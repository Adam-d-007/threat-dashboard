"""The whole hourly run on a small made-up state folder, with a model that answers from
rules, so every stage and every published file is exercised without a network."""

import json
from datetime import timedelta

import pytest

from monitor import run, status
from monitor.ai.client import AiUnavailable
from monitor.models import GeopoliticsFile, IncidentsFile, ReportsFile, Status, Summary
from monitor.tests.helpers import NOW, attack, item, label_dict
from monitor.tests.test_incidents import v1_event
from monitor.tests.test_scoring_v2 import assessment, history
from pipeline.models import RssBuffer, SourceHealth, Timeseries

AT = NOW.replace(hour=14, minute=30)   # 14:30 UTC: the 13:05 slot is due


def _data(user: str) -> object:
    return json.loads(user.split("\n", 1)[1].rsplit("\n", 1)[0])


class RuleAi:
    """Answers each task by simple rules on what it was sent."""

    keys = {"groq": "k"}
    down: set = set()

    def __init__(self):
        self.asked = []

    @classmethod
    def from_env(cls, cfg):
        return cls()

    @property
    def models(self):
        return {"groq_120b": type("M", (), {"model": "openai/gpt-oss-120b"})()}

    def clock(self):
        return 0.0

    def usable(self, task):
        return [] if task in self.down else ["groq_120b"]

    def report(self):
        return {"groq_120b": {"calls": len(self.asked)}}

    def ask(self, task, system, user, schema, name, parse, deadline=None):
        self.asked.append(task)
        if task in self.down:
            raise AiUnavailable(f"{task} is down")
        data = _data(user)
        if task == "label":
            out = []
            for row in data:
                if "zomrel" in row["title"]:
                    out.append(attack(row["id"], kind="update", summary_en="The shooter died."))
                elif "Lubline" in row["title"]:
                    out.append(attack(row["id"], incident_place="Lublin",
                                      incident_date="2026-11-13"))
                elif "Strelec" in row["title"]:
                    out.append(attack(row["id"]))
                else:
                    out.append(label_dict(row["id"], countries=["UA", "RU"],
                                          summary_en="Talks on Ukraine continued."))
            text = json.dumps({"items": out})
        elif task == "match":
            def known(r):
                same = [i["id"] for i in data["incidents"]
                        if (i["country"], i["date"]) == (r["country"], r["date"])]
                return same[0] if same else "new"
            text = json.dumps({"matches": [{"id": r["id"], "incident": known(r)}
                                           for r in data["reports"]]})
        elif task == "assess":
            text = assessment(drivers=[])
        else:
            text = json.dumps({
                "lines": [{"text_en": "Talks continued.", "text_sk": "Rokovania pokračovali.",
                           "item_ids": ["1"]}],
                "top_items": [{"item_id": "1", "summary_en": "Talks.", "summary_sk": "Rokovania."}],
                "sk_angle_en": None, "sk_angle_sk": None,
                "upcoming": [{"date": "2026-12-03", "title_en": "Summit", "title_sk": "Samit",
                              "item_id": "1"}]})
        return parse(text), "groq_120b"


SIS = {"id": "anchor_sk_sis", "country": "SK", "name": "SIS NBAC",
       "url": "https://www.sis.gov.sk/o-nas/nbac-sto.html", "scale": ["1", "2", "3", "4"],
       "raw": "2", "level": 2, "normalized": 0.333, "since": "2017-08-23",
       "as_of": "2026-11-12T13:05:00Z", "status": "ok"}


def build_state(tmp_path):
    """What the old pipeline leaves on the data branch."""
    items = [item("Strelec v Krakove zabil päť ľudí", hours_ago=3, also=("sme.sk",)),
             item("Údajný strelec z Krakova zomrel v nemocnici", hours_ago=2, domain="sme.sk"),
             item("Rokovania o vojne na Ukrajine pokračujú", hours_ago=1, domain="dennikn.sk"),
             item("Počasie na víkend", hours_ago=1, domain="pravda.sk")]
    buffer = RssBuffer(schema_version=1, updated_at=AT, items=items)
    (tmp_path / "rss_buffer.json").write_text(buffer.model_dump_json())
    press = [SourceHealth(id=f"s{n}", name=f"S{n}", tier="B", group="slovak_press", status="ok",
                          last_success=AT, items=5) for n in range(10)]
    (tmp_path / "source_health.json").write_text(json.dumps(
        {"schema_version": 1, "sources": [s.model_dump(mode="json") for s in press]}))
    (tmp_path / "latest.json").write_text(json.dumps({"anchors": [SIS], "run": {"id": "x"}}))
    events = [v1_event("evt_old", 3, country="FR", date=AT.date() - timedelta(days=5)),
              v1_event("evt_zero", 0, event_type="other")]
    (tmp_path / "events.json").write_text(json.dumps(
        {"schema_version": 1, "events": [e.model_dump(mode="json") for e in events]}))
    (tmp_path / "timeseries.json").write_text(json.dumps(
        {"schema_version": 1, "rows": history(), "sample": False}))
    (tmp_path / "scoring_state.json").write_text(json.dumps(
        {"regions": {"SK": {"level": 2, "index": 30, "below_runs": 0},
                     "EU": {"level": 2, "index": 30, "below_runs": 0}}, "anchor_history": {}}))
    return tmp_path


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "Ai", RuleAi)
    monkeypatch.setattr(RuleAi, "down", set())
    return build_state(tmp_path)


def go(state, *flags, at=AT):
    return run.main(["--state-dir", str(state), "--git-sha", "abc", "--now", at.isoformat(),
                     "--commit-msg-file", str(state / "msg.txt"), *flags])


def public(state, name, model):
    return model.model_validate(json.loads((state / "v2" / name).read_text()))


def test_one_hourly_run_from_news_to_published_files(state):
    assert go(state) == 0
    st = public(state, "status.json", Status)
    assert st.overall == "ok" and st.reasons == []
    assert {k: v.status for k, v in st.stages.items()} == {
        "ingest": "ok", "label": "ok", "match": "ok", "score": "ok", "brief": "ok",
        "publish": "ok"}
    assert st.queue.waiting_label == 0 and st.queue.labelled_24h == 3
    assert st.labelled_by_24h == {"groq_120b": 3} and st.last_scored == "2026-11-12T13"

    incidents = public(state, "incidents/current.json", IncidentsFile).incidents
    # One Kraków incident with its follow-up under it, and the incident carried over from the
    # old pipeline; its severity 0 "event" did not come along.
    assert [(i.country, len(i.reports)) for i in incidents] == [("PL", 2), ("FR", 2)]
    krakow = incidents[0]
    assert [r.kind for r in krakow.reports] == ["new_incident", "update"]
    assert krakow.corroborated and krakow.date.isoformat() == "2026-11-07"
    assert (state / "v2" / "incidents" / "2026-11.json").exists()

    reports = public(state, "reports.json", ReportsFile).reports
    assert len(reports) == 3 and {r.incident_id for r in reports} == {krakow.id, None}

    summary = public(state, "summary.json", Summary)
    assert summary.run_id == "2026-11-12T13" and summary.terrorism.SK.llm.status == "ok"
    assert summary.terrorism.SK.llm.model == "openai/gpt-oss-120b"
    rows = public(state, "history.json", Timeseries).rows
    assert [r.run_id for r in rows[-2:]] == ["2026-11-12T13"] * 2

    geo = public(state, "geopolitics.json", GeopoliticsFile)
    ua = next(t for t in geo.theatres if t.id == "russia_ukraine")
    assert ua.lines[0].text_sk == "Rokovania pokračovali." and ua.written_by == "openai/gpt-oss-120b"
    assert ua.lines[0].urls == [reports[0].url]
    assert any(w.origin == "news" and w.title_en == "Summit" for w in geo.watchlist)
    # Nothing outside v2/ was touched, and the commit message says what happened.
    assert not (state / "runs").exists()
    assert (state / "msg.txt").read_text().startswith(
        "monitor 2026-11-12T14:30 ok: +3 articles, 3 labelled, 0 waiting, 1 new incidents, "
        "1 reports added, scored 2026-11-12T13: SK ")


def test_a_second_run_within_forty_minutes_does_nothing(state):
    go(state)
    before = (state / "v2" / "status.json").read_text()
    assert go(state, at=AT + timedelta(minutes=20)) == 0
    assert (state / "v2" / "status.json").read_text() == before


def test_the_next_hour_scores_nothing_and_keeps_the_levels(state):
    go(state)
    assert go(state, at=AT + timedelta(hours=1)) == 0
    st = public(state, "status.json", Status)
    assert st.stages["score"].status == "skipped" and st.overall == "ok"
    assert public(state, "summary.json", Summary).run_id == "2026-11-12T13"
    assert len(public(state, "history.json", Timeseries).rows) == len(history()) + 2
    # The brief's text is carried, with the time it was written.
    ua = next(t for t in public(state, "geopolitics.json", GeopoliticsFile).theatres
              if t.id == "russia_ukraine")
    assert ua.lines and ua.written_at == AT


def test_without_ai_articles_wait_and_the_run_says_so(state):
    assert go(state, "--no-ai") == 0
    st = public(state, "status.json", Status)
    assert st.overall == "degraded" and st.reasons[0] == "the AI is switched off or has no key"
    assert st.queue.waiting_label == 3 and st.stages["label"].status == "skipped"
    # No article became an incident without a model: only the carried-over one is listed.
    assert [i.country for i in public(state, "incidents/current.json", IncidentsFile).incidents
            ] == ["FR"]


def test_when_the_models_are_down_the_work_waits_for_the_next_hour(state, monkeypatch):
    monkeypatch.setattr(RuleAi, "down", {"label", "match", "assess", "brief"})
    assert go(state) == 0
    st = public(state, "status.json", Status)
    assert st.overall == "degraded" and st.stages["label"].status == "degraded"
    assert "the last scoring had no model assessment for SK and EU" in st.reasons
    monkeypatch.setattr(RuleAi, "down", set())
    assert go(state, at=AT + timedelta(hours=1)) == 0
    st = public(state, "status.json", Status)
    assert st.queue.waiting_label == 0 and st.queue.labelled_24h == 3
    assert len(public(state, "incidents/current.json", IncidentsFile).incidents) == 2


def test_a_stage_that_crashes_is_reported_and_the_labels_are_kept(state, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no theatres file")
    monkeypatch.setattr(run, "brief", boom)
    assert go(state) == 1
    st = public(state, "status.json", Status)
    assert st.overall == "failed"
    assert st.reasons[0] == "brief failed: RuntimeError: no theatres file"
    assert st.queue.labelled_24h == 3 and st.stages["publish"].status == "ok"


def test_a_forced_scoring_replaces_the_slots_rows(state):
    go(state)
    assert go(state, "--force", "--force-score", at=AT + timedelta(minutes=5)) == 0
    rows = public(state, "history.json", Timeseries).rows
    assert [r.run_id for r in rows].count("2026-11-12T13") == 2


def test_the_alert_opens_only_after_a_day_without_one_good_run():
    def entry(hours_ago, overall):
        return {"at": (NOW - timedelta(hours=hours_ago)).isoformat(), "overall": overall}
    assert not status.alert_due([], NOW, 24)
    assert not status.alert_due([entry(3, "degraded"), entry(1, "degraded")], NOW, 24)
    assert not status.alert_due([entry(30, "degraded"), entry(5, "ok"), entry(1, "failed")], NOW, 24)
    assert status.alert_due([entry(30, "ok"), entry(20, "degraded"), entry(1, "failed")], NOW, 24)


def test_in_the_old_pipelines_hours_no_model_is_asked_and_articles_wait(state):
    assert go(state, at=AT.replace(hour=13)) == 0
    st = public(state, "status.json", Status)
    assert st.stages["label"].status == "skipped" and "old pipeline" in st.stages["label"].detail
    assert st.queue.waiting_label == 3
    assert go(state, at=AT) == 0
    assert public(state, "status.json", Status).queue.waiting_label == 0


def test_the_summary_says_what_changed_since_the_previous_scoring(state):
    go(state)
    first = public(state, "summary.json", Summary)
    assert first.diff.new_event_ids == [] and first.diff.level_changes == []
    # A day later: a source has failed, and an incident has been seen since.
    health = json.loads((state / "source_health.json").read_text())
    health["sources"][0]["status"] = "failed"
    (state / "source_health.json").write_text(json.dumps(health))
    extra = item("Strelec v Lubline zabil dvoch ľudí", hours_ago=-20)
    buffer = RssBuffer.model_validate_json((state / "rss_buffer.json").read_text())
    buffer.items.append(extra)
    (state / "rss_buffer.json").write_text(buffer.model_dump_json())
    go(state, at=AT + timedelta(hours=24))
    diff = public(state, "summary.json", Summary).diff
    assert [(c.id, c.value_from, c.value_to) for c in diff.source_changes] == [("s0", "ok", "failed")]
    assert len(diff.new_event_ids) == 1
    # The next hour does not score, and the changes stay as they were.
    go(state, at=AT + timedelta(hours=25))
    assert public(state, "summary.json", Summary).diff == diff


def test_the_second_run_does_not_reach_back_before_the_pipeline_started(state):
    buffer = RssBuffer.model_validate_json((state / "rss_buffer.json").read_text())
    buffer.items.append(item("Strelec v Lubline zabil dvoch ľudí", hours_ago=20))
    (state / "rss_buffer.json").write_text(buffer.model_dump_json())
    go(state)
    go(state, at=AT + timedelta(hours=1))
    st = public(state, "status.json", Status)
    # The article from 20 hours before the first run is never taken in.
    assert st.queue.labelled_24h == 3 and st.queue.waiting_label == 0
