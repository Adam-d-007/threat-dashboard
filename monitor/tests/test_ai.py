import json

import pytest

from monitor.ai.client import Ai, AiUnavailable, OutOfTime, Reply, clean
from monitor.ai.tasks import (
    BRIEF_SCHEMA,
    TheatreBrief,
    match_schema,
    parse_assessment,
    parse_brief,
    parse_matches,
)

CFG = {
    "models": {
        "groq_120b": {"provider": "groq", "model": "openai/gpt-oss-120b", "interval_s": 62,
                      "timeout_s": 60},
        "gemini_36": {"provider": "gemini", "model": "gemini-3.6-flash", "thinking": "MINIMAL",
                      "interval_s": 8, "timeout_s": 120},
    },
    "tasks": {"label": {"models": ["groq_120b", "gemini_36"], "max_output": 4096}},
    "strikes": 2,
    "max_wait_s": 90,
}
KEYS = {"groq": "gk", "gemini": "mk"}
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"],
          "additionalProperties": False}


def groq_ok(text='{"ok": true}', finish="stop"):
    return Reply(200, body={"choices": [{"message": {"content": text}, "finish_reason": finish}],
                            "usage": {"prompt_tokens": 100, "completion_tokens": 20}})


def gemini_ok(text='{"ok": true}'):
    return Reply(200, body={"candidates": [{"content": {"parts": [{"text": text}]},
                                            "finishReason": "STOP"}],
                            "usageMetadata": {"promptTokenCount": 90, "candidatesTokenCount": 15,
                                              "thoughtsTokenCount": 5}})


class Fake:
    """A provider that gives the queued replies in order, on a clock that only sleep moves."""

    def __init__(self, *replies):
        self.replies, self.sent, self.t, self.slept = list(replies), [], 1000.0, []

    def post(self, url, headers, body, timeout):
        self.sent.append((url, headers, body, timeout))
        return self.replies.pop(0)

    def clock(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


def ai(fake, keys=KEYS):
    return Ai(CFG, keys, post=fake.post, clock=fake.clock, sleep=fake.sleep)


def ask(client, **kw):
    return client.ask("label", "sys", "user", SCHEMA, "labels", json.loads, **kw)


def test_groq_is_asked_first_with_the_schema_in_strict_mode():
    fake = Fake(groq_ok())
    client = ai(fake)
    assert ask(client) == ({"ok": True}, "groq_120b")
    url, headers, body, timeout = fake.sent[0]
    assert url.endswith("/chat/completions") and headers == {"Authorization": "Bearer gk"}
    assert body["response_format"] == {"type": "json_schema", "json_schema": {
        "name": "labels", "strict": True, "schema": SCHEMA}}
    assert body["model"] == "openai/gpt-oss-120b" and body["max_completion_tokens"] == 4096
    assert timeout == 60
    assert client.report()["groq_120b"] == {
        "model": "openai/gpt-oss-120b", "calls": 1, "answered": 1, "tokens_in": 100,
        "tokens_out": 20, "out": None}


def test_gemini_gets_the_schema_and_minimal_thinking_and_its_thinking_counts_as_output():
    fake = Fake(gemini_ok())
    client = ai(fake, {"gemini": "mk"})
    assert ask(client) == ({"ok": True}, "gemini_36")
    url, headers, body, timeout = fake.sent[0]
    assert url.endswith("/models/gemini-3.6-flash:generateContent")
    assert headers == {"x-goog-api-key": "mk"} and timeout == 120
    assert body["generationConfig"] == {
        "responseMimeType": "application/json", "responseJsonSchema": SCHEMA,
        "maxOutputTokens": 8192, "thinkingConfig": {"thinkingLevel": "MINIMAL"}}
    assert client.report()["gemini_36"]["tokens_out"] == 20


def test_a_failing_model_hands_over_and_is_left_alone_after_two_failures():
    fake = Fake(Reply(503, text="busy"), gemini_ok(), Reply("timeout"), gemini_ok(), gemini_ok())
    client = ai(fake)
    assert ask(client)[1] == "gemini_36"
    assert ask(client)[1] == "gemini_36"
    assert client.models["groq_120b"].out == "failed 2 times in a row"
    assert ask(client)[1] == "gemini_36"
    # The third request never went to Groq.
    assert [s[0].split("/")[2] for s in fake.sent].count("api.groq.com") == 2


def test_an_answer_resets_the_count_of_failures():
    fake = Fake(Reply(503), gemini_ok(), groq_ok(), Reply(503), gemini_ok())
    client = ai(fake)
    for _ in range(3):
        ask(client)
    assert client.models["groq_120b"].out is None and client.models["groq_120b"].strikes == 1


def test_a_rate_limit_that_says_when_to_come_back_is_waited_out_once():
    fake = Fake(Reply(429, {"retry-after": "20"}, text="slow down"), groq_ok())
    client = ai(fake)
    assert ask(client)[1] == "groq_120b"
    assert fake.slept == [21.0]
    assert client.models["groq_120b"].out is None


def test_a_rate_limit_with_no_way_back_drops_the_model_for_the_run():
    fake = Fake(Reply(429, {"retry-after": "3600"}, text="daily limit"), gemini_ok(), gemini_ok())
    client = ai(fake)
    assert ask(client)[1] == "gemini_36"
    assert client.models["groq_120b"].out == "rate limit reached"
    assert ask(client)[1] == "gemini_36"
    assert len(fake.sent) == 3


def test_a_request_too_large_for_one_model_is_not_held_against_it():
    fake = Fake(Reply(413, text="Request too large in organization `org_abc123`"), gemini_ok())
    client = ai(fake)
    assert ask(client)[1] == "gemini_36"
    assert client.models["groq_120b"].out is None and client.models["groq_120b"].strikes == 0


def test_a_refused_key_drops_the_model_at_once():
    fake = Fake(Reply(401, text="bad key"), gemini_ok())
    client = ai(fake)
    ask(client)
    assert client.models["groq_120b"].out == "HTTP 401 (key refused)"


def test_an_answer_that_was_cut_off_goes_to_the_next_model():
    fake = Fake(groq_ok('{"ok": tr', finish="length"), gemini_ok())
    assert ask(ai(fake)) == ({"ok": True}, "gemini_36")


MISFIT = Reply(400, text='{"error":{"message":"Generated JSON does not match the expected '
               'schema.","code":"json_validate_failed"}}')


def test_an_answer_that_does_not_fit_is_asked_for_once_more_from_the_same_model():
    fake = Fake(MISFIT, groq_ok())
    client = ai(fake)
    assert ask(client) == ({"ok": True}, "groq_120b")
    assert client.models["groq_120b"].strikes == 0 and fake.slept == [62.0]
    fake = Fake(groq_ok("not json"), groq_ok())
    assert ask(ai(fake)) == ({"ok": True}, "groq_120b")


def test_two_misfits_in_a_row_are_one_failure_and_the_next_model_is_asked():
    fake = Fake(MISFIT, groq_ok("not json"), gemini_ok())
    client = ai(fake)
    assert ask(client)[1] == "gemini_36"
    assert client.models["groq_120b"].strikes == 1 and client.models["groq_120b"].answered == 0


def test_when_every_model_fails_the_last_reason_is_raised_without_the_organisation_id():
    fake = Fake(Reply(503, text="busy"), Reply(500, text="error for org_abc123"))
    with pytest.raises(AiUnavailable, match=r"gemini_36: HTTP 500 error for org_\(hidden\)"):
        ask(ai(fake))


def test_without_a_key_no_model_is_asked():
    fake = Fake()
    with pytest.raises(AiUnavailable, match="no model has a key"):
        ask(ai(fake, {}))
    assert fake.sent == []


def test_calls_to_one_model_keep_their_distance():
    fake = Fake(groq_ok(), groq_ok())
    client = ai(fake)
    ask(client)
    fake.t += 10
    ask(client)
    assert fake.slept == [52.0]


def test_a_call_that_cannot_start_before_the_deadline_is_not_made():
    fake = Fake(groq_ok())
    client = ai(fake)
    ask(client)
    with pytest.raises(OutOfTime):
        ask(client, deadline=fake.t + 30)
    assert len(fake.sent) == 1


def test_error_text_for_the_public_log_hides_the_organisation_id():
    assert clean("Request too large in organization `org_01abcXYZ`\n on TPM") == (
        "Request too large in organization `org_(hidden)` on TPM")


def test_a_match_may_only_name_a_listed_incident_or_new():
    entry = match_schema(["inc1", "inc2"])["properties"]["matches"]["items"]
    assert entry["properties"]["incident"]["enum"] == ["inc1", "inc2", "new"]
    text = json.dumps({"matches": [{"id": "r1", "incident": "inc2"}, {"id": "r2", "incident": "new"},
                                   {"id": "r3", "incident": "inc9"}, {"id": "zz", "incident": "new"}]})
    assert parse_matches(text, {"r1", "r2", "r3"}, {"inc1", "inc2"}) == {"r1": "inc2", "r2": "new"}
    with pytest.raises(ValueError, match="no usable match"):
        parse_matches('{"matches": []}', {"r1"}, {"inc1"})


def test_a_theatre_brief_and_an_assessment_are_validated():
    brief = {"lines": [{"text_en": "A.", "text_sk": "A.", "item_ids": ["1"]}], "top_items": [],
             "sk_angle_en": None, "sk_angle_sk": None,
             "upcoming": [{"date": "2026-11-26", "title_en": "Summit", "title_sk": "Samit",
                           "item_id": "1"}]}
    assert isinstance(parse_brief(json.dumps(brief)), TheatreBrief)
    assert list(BRIEF_SCHEMA["properties"]) == list(TheatreBrief.model_fields)
    with pytest.raises(ValueError):
        parse_brief(json.dumps(brief | {"upcoming": [brief["upcoming"][0] | {"date": "soon"}]}))
    out = parse_assessment(json.dumps({
        "level": 2, "position": "mid", "confidence": "medium", "what_changed_en": "x",
        "what_changed_sk": "x", "drivers": [{"text_en": "a", "text_sk": "a", "event_ids": ["e"]}]}))
    assert out.level == 2 and out.drivers[0].event_ids == ["e"]
    with pytest.raises(ValueError):
        parse_assessment('{"level": 7}')
