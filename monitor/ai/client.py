"""AI access: a fixed list of free models per task, each asked with the provider's strict JSON
mode, so the answer's shape is enforced by the provider and not hoped for.

Keys come from ANTHROPIC_API_KEY, GEMINI_API_KEY and GROQ_API_KEY. Claude (on MCS's API
credit, from 2026-11-21) is asked first and the free models are the backup: in the week to
2026-11-20 their daily allowances ran out in 9 of 14 scoring runs. Claude is called through the
official SDK with a JSON Schema as structured output (output_config.format), which constrains
its answer to the schema. A monthly cap on its estimated cost keeps it within the credit.
Policy, from the old pipeline's runs and the step 0 probe (2026-11-12):
- Models are asked in the task's order. The first usable answer wins; its model is returned
  with it, so every label records who wrote it.
- Each model has a least interval between calls (Groq: 8,000 tokens a minute).
- A rate limit that says when to come back, within max_wait_s, is waited out once. Any other
  429 means the day's or minute's allowance is gone: the model is left alone for the run.
- 5xx, timeouts and network errors are a strike; `strikes` in a row leave the model alone for
  the run. 401 and 403 (bad key) do so at once. 413 (too large for this model) only skips it
  for this request.
- An answer that does not fit (the provider's own schema check refuses it, or `parse` does)
  is asked for once more from the same model; a second misfit, or an answer that was cut off,
  is a strike and the next model is asked. Strict mode makes this rare; it is never papered
  over.
When no model is left, AiUnavailable is raised and the caller leaves the work waiting.
"""

import logging
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import anthropic
import httpx

from pipeline.adapters.base import TLS, USER_AGENT

log = logging.getLogger("monitor.ai")

GEMINI = "https://generativelanguage.googleapis.com/v1beta"
GROQ = "https://api.groq.com/openai/v1"
GEMINI_MAX_OUTPUT = 8192
DONE = {"groq": "stop", "gemini": "STOP", "anthropic": "end_turn"}
# On a refusal Opus 5.5's answer is rerun on another Claude model inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AiUnavailable(Exception):
    """No model could answer this request."""


class OutOfTime(AiUnavailable):
    """The next call could not start before the caller's deadline."""


@dataclass
class Reply:
    status: int | str                      # HTTP status, or "timeout" / the network error's name
    headers: dict = field(default_factory=dict)
    body: dict | None = None               # parsed JSON of a 200
    text: str = ""                         # body of anything else


def clean(text: str) -> str:
    """Error text for a public log: one line, no organisation id."""
    return re.sub(r"org_\w+", "org_(hidden)", " ".join(text.split()))[:300]


def http_post(url: str, headers: dict, body: dict, timeout: float) -> Reply:
    try:
        r = httpx.post(url, headers={"User-Agent": USER_AGENT, **headers}, json=body,
                       timeout=timeout, verify=TLS)
    except httpx.TimeoutException:
        return Reply("timeout")
    except httpx.HTTPError as e:
        return Reply(type(e).__name__)
    if r.status_code == 200:
        return Reply(200, dict(r.headers), body=r.json())
    return Reply(r.status_code, dict(r.headers), text=r.text)


def claude_schema(schema: dict) -> dict:
    """The schema as Claude's structured outputs take it: a list of types (["string", "null"],
    which Groq and Gemini read) becomes anyOf, which Claude's documented subset includes."""
    if isinstance(schema.get("type"), list):
        rest = {k: v for k, v in schema.items() if k not in ("type", "enum")}
        branches = []
        for t in schema["type"]:
            branch = {"type": t}
            if t != "null" and "enum" in schema:
                branch["enum"] = [v for v in schema["enum"] if v is not None]
            branches.append(branch)
        return {**rest, "anyOf": branches}
    out = dict(schema)
    if "properties" in out:
        out["properties"] = {k: claude_schema(v) for k, v in out["properties"].items()}
    if "items" in out:
        out["items"] = claude_schema(out["items"])
    return out


def claude_post(key: str, body: dict, timeout: float) -> Reply:
    """One Claude call through the SDK, in the same shape as the other providers' replies.
    The SDK retries a connection error, 429 or 5xx once by itself; anything further is the
    policy above."""
    client = anthropic.Anthropic(api_key=key, timeout=timeout, max_retries=1)
    try:
        if "fallbacks" in body:
            msg = client.beta.messages.create(**body, betas=[FALLBACK_BETA])
        else:
            msg = client.messages.create(**body)
    except anthropic.APITimeoutError:
        return Reply("timeout")
    except anthropic.APIConnectionError as e:
        return Reply(type(e).__name__)
    except anthropic.APIStatusError as e:
        # The spend limit set in the Console, or the credit used up: no point asking again.
        spent = isinstance(e, (anthropic.EnforcedSpendLimitReachedError,
                               anthropic.ContractSpendLimitReachedError,
                               anthropic.PaymentRequiredError)) or "credit balance" in str(e)
        return Reply(e.status_code, dict(e.response.headers),
                     text=("SPENT " if spent else "") + str(e.message))
    usage = msg.usage
    return Reply(200, body={
        "text": "".join(b.text for b in msg.content if b.type == "text"),
        "stop_reason": msg.stop_reason,
        "tokens_in": (usage.input_tokens or 0) + (usage.cache_read_input_tokens or 0)
        + (usage.cache_creation_input_tokens or 0),
        "tokens_out": usage.output_tokens or 0})


@dataclass
class Model:
    name: str
    provider: str
    model: str
    interval_s: float
    timeout_s: float
    thinking: str | None = None            # Gemini: thinkingLevel; Claude: thinking.type
    effort: str | None = None              # Claude: output_config.effort
    fallbacks: bool = False                # Claude: server-side fallback on a refusal
    max_output: int | None = None          # overrides the task's, for models that think
    price: tuple[float, float] = (0.0, 0.0)  # US dollars per million tokens in and out
    last_call: float | None = None
    strikes: int = 0
    out: str | None = None                 # why it is left alone for the rest of the run
    calls: int = 0
    answered: int = 0
    tokens_in: int = 0
    tokens_out: int = 0

    @property
    def cost_usd(self) -> float:
        return (self.tokens_in * self.price[0] + self.tokens_out * self.price[1]) / 1e6


def request(m: Model, key: str, system: str, user: str, schema: dict, name: str,
            max_output: int) -> tuple[str, dict, dict]:
    """(url, headers, body) of one strict-JSON call. For Claude the body holds the SDK's
    arguments and the url only names the provider."""
    if m.provider == "anthropic":
        body = {"model": m.model, "max_tokens": max_output, "system": system,
                "messages": [{"role": "user", "content": user}],
                "output_config": {"format": {"type": "json_schema",
                                             "schema": claude_schema(schema)}}}
        if m.effort:
            body["output_config"]["effort"] = m.effort
        if m.thinking:
            # Sonnet 5.5's lowest setting, "between_tools": no thinking before the answer.
            body["thinking"] = {"type": m.thinking}
        if m.fallbacks:
            body["fallbacks"] = "default"
        return "anthropic", {}, body
    if m.provider == "groq":
        return f"{GROQ}/chat/completions", {"Authorization": f"Bearer {key}"}, {
            "model": m.model, "temperature": 0, "max_completion_tokens": max_output,
            "response_format": {"type": "json_schema", "json_schema": {
                "name": name, "strict": True, "schema": schema}},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}]}
    config = {"responseMimeType": "application/json", "responseJsonSchema": schema,
              "maxOutputTokens": GEMINI_MAX_OUTPUT}
    if m.thinking:
        config["thinkingConfig"] = {"thinkingLevel": m.thinking}
    return f"{GEMINI}/models/{m.model}:generateContent", {"x-goog-api-key": key}, {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": config}


def answer(provider: str, body: dict) -> tuple[str, str | None, int, int]:
    """(text, finish reason, input tokens, output tokens) of a 200 response."""
    if provider == "anthropic":
        return body["text"], body["stop_reason"], body["tokens_in"], body["tokens_out"]
    if provider == "groq":
        choice = body["choices"][0]
        usage = body.get("usage") or {}
        return (choice["message"].get("content") or "", choice.get("finish_reason"),
                usage.get("prompt_tokens") or 0, usage.get("completion_tokens") or 0)
    cands = body.get("candidates") or []
    usage = body.get("usageMetadata") or {}
    parts = (cands[0].get("content") or {}).get("parts", []) if cands else []
    return ("".join(p.get("text", "") for p in parts),
            cands[0].get("finishReason") if cands else "no candidate",
            usage.get("promptTokenCount") or 0,
            (usage.get("candidatesTokenCount") or 0) + (usage.get("thoughtsTokenCount") or 0))


class Ai:
    def __init__(self, cfg: dict, keys: dict[str, str], post: Callable = http_post,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep,
                 claude: Callable = claude_post):
        self.cfg, self.keys = cfg, keys
        self.post, self.clock, self.sleep, self.claude = post, clock, sleep, claude
        self.models = {name: Model(name=name, **{k: tuple(v) if k == "price" else v
                                                 for k, v in spec.items()})
                       for name, spec in cfg["models"].items()}

    @classmethod
    def from_env(cls, cfg: dict) -> "Ai":
        keys = {p: os.environ[f"{p.upper()}_API_KEY"] for p in ("anthropic", "gemini", "groq")
                if os.environ.get(f"{p.upper()}_API_KEY")}
        return cls(cfg, keys)

    def cap(self, provider: str, spent_usd: float) -> None:
        """Leave a paid provider's models alone for the run once this month's estimated spend
        has reached the configured cap."""
        limit = self.cfg.get("monthly_cap_usd", {}).get(provider)
        if limit is not None and spent_usd >= limit:
            for m in self.models.values():
                if m.provider == provider:
                    m.out = f"monthly cap of ${limit} reached (${spent_usd:.2f} spent)"
            log.warning("%s left alone: this month's estimated spend $%.2f reached the cap $%s",
                        provider, spent_usd, limit)

    def usable(self, task: str) -> list[Model]:
        return [self.models[n] for n in self.cfg["tasks"][task]["models"]
                if self.models[n].provider in self.keys and not self.models[n].out]

    def ask(self, task: str, system: str, user: str, schema: dict, name: str,
            parse: Callable[[str], object], deadline: float | None = None) -> tuple[object, str]:
        """(parse(answer), name of the model that gave it). parse raises ValueError on an
        answer it cannot use."""
        last = "no model has a key and is still in use"
        for m in self.usable(task):
            max_output = m.max_output or self.cfg["tasks"][task]["max_output"]
            url, headers, body = request(m, self.keys[m.provider], system, user, schema, name,
                                         max_output)
            for attempt in (1, 2):
                reply = self._call(m, url, headers, body, deadline)
                after = self._retry_after(reply)
                if reply.status == 429 and after is not None and after <= self.cfg["max_wait_s"]:
                    log.info("%s is rate-limited; waiting %.0f s as asked", m.name, after)
                    self.sleep(after + 1)
                    reply = self._call(m, url, headers, body, deadline, paced=False)
                # Strict mode is not a hard promise: Groq sometimes answers 400
                # json_validate_failed when its model missed the schema (seen 2026-11-12, once
                # in about twenty calls). The same request usually works the second time.
                misfit = reply.status == 400 and "json_validate_failed" in reply.text
                if reply.status == 200:
                    text, finish, tokens_in, tokens_out = answer(m.provider, reply.body)
                    m.tokens_in += tokens_in
                    m.tokens_out += tokens_out
                    if finish != DONE[m.provider]:
                        last = f"{m.name}: answer cut off ({finish}, {tokens_out} output tokens)"
                        self._strike(m, last)
                        break
                    try:
                        result = parse(text)
                    except ValueError as e:
                        last = f"{m.name}: unusable answer: {clean(str(e))}"
                        misfit = True
                    else:
                        m.strikes = 0
                        m.answered += 1
                        return result, m.name
                else:
                    last = f"{m.name}: HTTP {reply.status} {clean(reply.text)}".strip()
                if misfit and attempt == 1:
                    log.info("%s: the answer did not fit; asking once more", m.name)
                    continue
                if misfit:
                    self._strike(m, last)
                else:
                    self._failed(m, reply)
                break
        raise AiUnavailable(last)

    def _call(self, m: Model, url: str, headers: dict, body: dict, deadline: float | None,
              paced: bool = True) -> Reply:
        wait = 0.0 if m.last_call is None or not paced else \
            m.last_call + m.interval_s - self.clock()
        if deadline is not None and self.clock() + max(wait, 0.0) > deadline:
            raise OutOfTime(f"{m.name} could not be asked before the deadline")
        if wait > 0:
            self.sleep(wait)
        m.last_call = self.clock()
        m.calls += 1
        if m.provider == "anthropic":
            return self.claude(self.keys["anthropic"], body, m.timeout_s)
        return self.post(url, headers, body, m.timeout_s)

    @staticmethod
    def _retry_after(reply: Reply) -> float | None:
        try:
            return float(reply.headers.get("retry-after", ""))
        except ValueError:
            return None

    def _failed(self, m: Model, reply: Reply) -> None:
        if reply.text.startswith("SPENT "):
            for other in self.models.values():
                if other.provider == m.provider:
                    other.out = "spend limit or credit reached"
            log.warning("%s left alone for this run: %s", m.provider, clean(reply.text))
        elif reply.status == 413:
            log.warning("%s: request too large for this model", m.name)
        elif reply.status == 429:
            m.out = "rate limit reached"
            # Which limit, and when it resets: the headers are the only place a free plan's
            # real limits are stated.
            limits = {k: v for k, v in reply.headers.items()
                      if k.lower().startswith("x-ratelimit-") or k.lower() == "retry-after"}
            log.warning("%s left alone for this run: rate limit reached %s %s", m.name, limits,
                        clean(reply.text))
        elif reply.status in (401, 403):
            m.out = f"HTTP {reply.status} (key refused)"
            log.warning("%s left alone for this run: %s", m.name, m.out)
        else:
            # Groq answers 400 json_validate_failed when its model could not fit the schema.
            self._strike(m, f"HTTP {reply.status} {clean(reply.text)}".strip())

    def _strike(self, m: Model, why: str) -> None:
        m.strikes += 1
        log.warning("%s failed (%d in a row): %s", m.name, m.strikes, why)
        if m.strikes >= self.cfg["strikes"]:
            m.out = f"failed {m.strikes} times in a row"
            log.warning("%s left alone for this run", m.name)

    def report(self) -> dict[str, dict]:
        """Per model: calls, answers, tokens and why it was dropped, for status.json."""
        return {m.name: {"model": m.model, "calls": m.calls, "answered": m.answered,
                         "tokens_in": m.tokens_in, "tokens_out": m.tokens_out, "out": m.out,
                         "cost_usd": round(m.cost_usd, 4)}
                for m in self.models.values() if m.calls}

    def cost_by_provider(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for m in self.models.values():
            out[m.provider] = out.get(m.provider, 0.0) + m.cost_usd
        return out
