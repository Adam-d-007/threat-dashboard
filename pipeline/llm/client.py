"""LLM access: Gemini first, Groq as fallback, JSON out.

Keys come from GEMINI_API_KEY and GROQ_API_KEY (GitHub secrets). Each provider is limited to
its configured requests per minute. Error policy, from the first live runs (2026-10-22, when
gemini-3.8-flash answered 503 "overloaded" for minutes):
- 429, 5xx and network errors are temporary: retry after 5 and 15 s, then try the provider's
  next model (e.g. gemini-2.5-flash), then the next provider. A provider whose every model
  failed a request is dropped for the rest of the run.
- 401 and 403 (bad key) drop the provider at once; 404 skips to its next model.
- All LLM work in a run stops after max_seconds, so a run stays inside its time budget.
- An answer that is not valid JSON is the model's fault, not the provider's: LlmBadOutput
  goes back to the caller, which retries once with the error and then uses the rules.
When no provider is left, LlmUnavailable is raised and the caller falls back to rules. The
model has no tools; prompts pass source text as data only.
"""

import logging
import os
import re
import time
from dataclasses import dataclass, field

import httpx

from ..adapters.base import TLS, USER_AGENT

log = logging.getLogger("pipeline.llm")

GEMINI = "https://generativelanguage.googleapis.com/v1beta"
GROQ = "https://api.groq.com/openai/v1"
TIMEOUT_S = 45
RETRY_WAITS_S = (5, 15)
# A 429 with a Retry-After of at most this many seconds is waited out instead of the fixed
# waits: Groq's free tier counts tokens per minute and says when the minute resets.
MAX_RETRY_AFTER_S = 60
MAX_OUTPUT_TOKENS = 8192
TRANSIENT = {429, 500, 502, 503, 504, None}
# A provider that has spent this long failing since its last answer is dropped for the run, so
# the next one always gets its turn. On 2026-10-24 Gemini timed out on four models and used the
# whole 480 s budget; Groq was never asked.
PROVIDER_MAX_FAILING_S = 150
FATAL = {401, 403}
_SKIP = re.compile(r"lite|image|tts|live|audio|embedding|exp|thinking|vision|guard")
MAX_MODELS = 4


class LlmUnavailable(Exception):
    pass


class LlmBadOutput(Exception):
    """The provider answered, but not with usable JSON."""


class _ProviderError(Exception):
    def __init__(self, message: str, status: int | str | None = None,
                 retry_after: float | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def _version(name: str) -> tuple[float, ...]:
    m = re.search(r"(\d+(?:\.\d+)?)", name)
    return (float(m.group(1)),) if m else (0.0,)


def pick_models(available: list[str], prefer: list[str], family: str | None) -> list[str]:
    """Preferred models that exist, in order, then the newest stable model of the family. With a
    family (Gemini), the family's other stable models follow as fallbacks, newest first and
    lite models last, up to MAX_MODELS: each has its own free-tier quota."""
    out = [p for p in prefer if p in available]
    pool = [m for m in available if (family is None or family in m) and not _SKIP.search(m)]
    stable = [m for m in pool if "preview" not in m] or pool
    if family is None:
        if stable and (newest := max(stable, key=_version)) not in out:
            out.append(newest)
        return out
    full = sorted((m for m in stable if m not in out), key=_version, reverse=True)
    lite = sorted((m for m in available if family in m and "lite" in m and m not in out
                   and "preview" not in m and not _SKIP.search(m.replace("lite", ""))),
                  key=_version, reverse=True)
    return (out + full + lite)[:MAX_MODELS]


def pick_model(available: list[str], prefer: list[str], family: str | None) -> str | None:
    models = pick_models(available, prefer, family)
    return models[0] if models else None


@dataclass
class _Provider:
    name: str
    key: str
    rpm: int
    prefer: list[str]
    family: str | None
    models: list[str] | None = None
    model_index: int = 0
    last_call: float = 0.0
    dead: bool = False
    failing_s: float = 0.0  # time spent in failed calls since the last answer

    @property
    def model(self) -> str | None:
        return self.models[self.model_index] if self.models else None


@dataclass
class LlmClient:
    cfg: dict
    calls: int = 0
    providers: list[_Provider] = field(default_factory=list)
    used: list[str] = field(default_factory=list)
    started: float = field(default_factory=time.monotonic)

    @property
    def out_of_time(self) -> bool:
        return time.monotonic() - self.started > self.cfg.get("max_seconds", 480)

    @classmethod
    def from_env(cls, cfg: dict) -> "LlmClient":
        c = cls(cfg)
        for name in ("gemini", "groq"):
            key = os.environ.get(f"{name.upper()}_API_KEY")
            if key:
                pc = cfg[name]
                c.providers.append(_Provider(name, key, pc["requests_per_minute"], pc["prefer"],
                                             pc.get("family")))
        return c

    @property
    def available(self) -> bool:
        return not self.out_of_time and any(not p.dead for p in self.providers)

    def usage(self) -> dict:
        return {"provider": self.used[-1].split(":")[0] if self.used else None,
                "model": self.used[-1].split(":", 1)[1] if self.used else None,
                "calls": self.calls,
                "fallback_used": len({u.split(":")[0] for u in self.used}) > 1
                or bool(self.used and self.used[0].split(":")[0] != "gemini")}

    def complete_json(self, system: str, user: str) -> str:
        """Raw JSON text from the first provider and model that answers."""
        for p in self.providers:
            if p.dead:
                continue
            try:
                if p.models is None:
                    p.models = self._resolve_models(p)
            except _ProviderError as e:
                p.dead = True
                log.warning("%s dropped: cannot list models: %s", p.name, e)
                continue
            while p.model_index < len(p.models):
                if self.out_of_time:
                    raise LlmUnavailable("LLM time budget for this run used up")
                started = time.monotonic()
                try:
                    text = self._call_with_retry(p, system, user)
                    p.failing_s = 0.0
                    self.used.append(f"{p.name}:{p.model}")
                    return text
                except _ProviderError as e:
                    p.failing_s += time.monotonic() - started
                    if e.status in FATAL:
                        log.warning("%s dropped (bad key?): %s", p.name, e)
                        p.model_index = len(p.models)
                        break
                    if p.failing_s > PROVIDER_MAX_FAILING_S:
                        log.warning("%s has failed for %.0f s; next provider", p.name, p.failing_s)
                        p.model_index = len(p.models)
                        break
                    log.warning("%s %s failed, trying the next model: %s", p.name, p.model, e)
                    p.model_index += 1
            p.dead = True
            log.warning("%s dropped for the rest of the run: no model answered", p.name)
        raise LlmUnavailable("no LLM provider answered")

    def _resolve_models(self, p: _Provider) -> list[str]:
        if p.name == "gemini":
            r = self._http("GET", f"{GEMINI}/models", p, params={"pageSize": 1000})
            names = [m["name"].removeprefix("models/") for m in r.json().get("models", [])
                     if "generateContent" in m.get("supportedGenerationMethods", [])]
        else:
            r = self._http("GET", f"{GROQ}/models", p)
            names = [m["id"] for m in r.json().get("data", [])]
        models = pick_models(names, p.prefer, p.family)
        if not models:
            raise _ProviderError("no suitable model in the provider's model list")
        if models[0] not in p.prefer:
            log.warning("%s: preferred models %s not available", p.name, p.prefer)
        log.info("%s models, in order: %s", p.name, models)
        return models

    def _call_with_retry(self, p: _Provider, system: str, user: str) -> str:
        for wait in (*RETRY_WAITS_S, None):
            try:
                return self._call(p, system, user)
            except _ProviderError as e:
                # A timeout (status "timeout", not in TRANSIENT) has already cost TIMEOUT_S, so
                # it moves to the next model instead of trying the same one again.
                if wait is None or e.status not in TRANSIENT or self.out_of_time:
                    raise
                if e.retry_after is not None and e.retry_after <= MAX_RETRY_AFTER_S:
                    wait = e.retry_after + 1
                log.info("%s answered %s; retrying in %d s", p.name, e.status, wait)
                time.sleep(wait)
        raise AssertionError("unreachable")

    def _call(self, p: _Provider, system: str, user: str) -> str:
        wait = p.last_call + 60 / p.rpm - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        p.last_call = time.monotonic()
        self.calls += 1
        if p.name == "gemini":
            r = self._http("POST", f"{GEMINI}/models/{p.model}:generateContent", p, json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                                     "maxOutputTokens": MAX_OUTPUT_TOKENS},
            })
            body = r.json()
            cands = body.get("candidates") or []
            if not cands or "content" not in cands[0]:
                reason = cands[0].get("finishReason") if cands else body.get("promptFeedback")
                raise LlmBadOutput(f"gemini returned no text: {str(reason)[:200]}")
            return "".join(part.get("text", "") for part in cands[0]["content"].get("parts", []))
        try:
            r = self._http("POST", f"{GROQ}/chat/completions", p, json={
                "model": p.model, "temperature": 0, "response_format": {"type": "json_object"},
                "max_completion_tokens": MAX_OUTPUT_TOKENS,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}],
            })
        except _ProviderError as e:
            if e.status == 400 and "json_validate_failed" in str(e):
                raise LlmBadOutput("groq: the model's answer was not valid JSON") from e
            raise
        return r.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _http(method: str, url: str, p: _Provider, **kw) -> httpx.Response:
        headers = {"User-Agent": USER_AGENT}
        if p.name == "gemini":
            headers["x-goog-api-key"] = p.key
        else:
            headers["Authorization"] = f"Bearer {p.key}"
        try:
            r = httpx.request(method, url, headers=headers, timeout=TIMEOUT_S, verify=TLS, **kw)
        except httpx.TimeoutException as e:
            raise _ProviderError(f"{type(e).__name__}", "timeout") from e
        except httpx.HTTPError as e:
            raise _ProviderError(f"{type(e).__name__}") from e
        if r.status_code != 200:
            # The body can echo the request, so keep only a short, key-free excerpt.
            try:
                retry_after = float(r.headers.get("retry-after", ""))
            except ValueError:
                retry_after = None
            raise _ProviderError(f"HTTP {r.status_code}: {r.text[:160]}", r.status_code,
                                 retry_after)
        return r
