"""AI access: a fixed list of free models per task, each asked with the provider's strict JSON
mode, so the answer's shape is enforced by the provider and not hoped for.

Keys come from GEMINI_API_KEY and GROQ_API_KEY. Policy, from the old pipeline's runs and the
step 0 probe (2026-11-12):
- Models are asked in the task's order. The first usable answer wins; its model is returned
  with it, so every label records who wrote it.
- Each model has a least interval between calls (Groq: 8,000 tokens a minute).
- A rate limit that says when to come back, within max_wait_s, is waited out once. Any other
  429 means the day's or minute's allowance is gone: the model is left alone for the run.
- 5xx, timeouts and network errors are a strike; `strikes` in a row leave the model alone for
  the run. 401 and 403 (bad key) do so at once. 413 (too large for this model) only skips it
  for this request.
- An answer that was cut off or does not pass `parse` is a strike too, and the next model is
  asked. Strict mode makes this rare; it is never papered over.
When no model is left, AiUnavailable is raised and the caller leaves the work waiting.
"""

import logging
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from pipeline.adapters.base import TLS, USER_AGENT

log = logging.getLogger("monitor.ai")

GEMINI = "https://generativelanguage.googleapis.com/v1beta"
GROQ = "https://api.groq.com/openai/v1"
GEMINI_MAX_OUTPUT = 8192
DONE = {"groq": "stop", "gemini": "STOP"}


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


@dataclass
class Model:
    name: str
    provider: str
    model: str
    interval_s: float
    timeout_s: float
    thinking: str | None = None
    last_call: float | None = None
    strikes: int = 0
    out: str | None = None                 # why it is left alone for the rest of the run
    calls: int = 0
    answered: int = 0
    tokens_in: int = 0
    tokens_out: int = 0


def request(m: Model, key: str, system: str, user: str, schema: dict, name: str,
            max_output: int) -> tuple[str, dict, dict]:
    """(url, headers, body) of one strict-JSON call."""
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
                 sleep: Callable[[float], None] = time.sleep):
        self.cfg, self.keys = cfg, keys
        self.post, self.clock, self.sleep = post, clock, sleep
        self.models = {name: Model(name=name, **spec) for name, spec in cfg["models"].items()}

    @classmethod
    def from_env(cls, cfg: dict) -> "Ai":
        keys = {p: os.environ[f"{p.upper()}_API_KEY"] for p in ("gemini", "groq")
                if os.environ.get(f"{p.upper()}_API_KEY")}
        return cls(cfg, keys)

    def usable(self, task: str) -> list[Model]:
        return [self.models[n] for n in self.cfg["tasks"][task]["models"]
                if self.models[n].provider in self.keys and not self.models[n].out]

    def ask(self, task: str, system: str, user: str, schema: dict, name: str,
            parse: Callable[[str], object], deadline: float | None = None) -> tuple[object, str]:
        """(parse(answer), name of the model that gave it). parse raises ValueError on an
        answer it cannot use."""
        max_output = self.cfg["tasks"][task]["max_output"]
        last = "no model has a key and is still in use"
        for m in self.usable(task):
            url, headers, body = request(m, self.keys[m.provider], system, user, schema, name,
                                         max_output)
            reply = self._call(m, url, headers, body, deadline)
            after = self._retry_after(reply)
            if reply.status == 429 and after is not None and after <= self.cfg["max_wait_s"]:
                log.info("%s is rate-limited; waiting %.0f s as asked", m.name, after)
                self.sleep(after + 1)
                reply = self._call(m, url, headers, body, deadline, paced=False)
            if reply.status != 200:
                last = f"{m.name}: HTTP {reply.status} {clean(reply.text)}".strip()
                self._failed(m, reply)
                continue
            text, finish, tokens_in, tokens_out = answer(m.provider, reply.body)
            m.tokens_in += tokens_in
            m.tokens_out += tokens_out
            if finish != DONE[m.provider]:
                last = f"{m.name}: answer cut off ({finish}, {tokens_out} output tokens)"
                self._strike(m, last)
                continue
            try:
                result = parse(text)
            except ValueError as e:
                last = f"{m.name}: unusable answer: {clean(str(e))}"
                self._strike(m, last)
                continue
            m.strikes = 0
            m.answered += 1
            return result, m.name
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
        return self.post(url, headers, body, m.timeout_s)

    @staticmethod
    def _retry_after(reply: Reply) -> float | None:
        try:
            return float(reply.headers.get("retry-after", ""))
        except ValueError:
            return None

    def _failed(self, m: Model, reply: Reply) -> None:
        if reply.status == 413:
            log.warning("%s: request too large for this model", m.name)
        elif reply.status == 429:
            m.out = "rate limit reached"
            log.warning("%s left alone for this run: rate limit reached", m.name)
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
                         "tokens_in": m.tokens_in, "tokens_out": m.tokens_out, "out": m.out}
                for m in self.models.values() if m.calls}
