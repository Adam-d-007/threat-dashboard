"""LLM access: Gemini first, Groq as fallback, JSON out.

Keys come from GEMINI_API_KEY and GROQ_API_KEY (GitHub secrets). Each provider is limited to
its configured requests per minute. Error policy, from the first live run (2026-10-22):
- 429, 5xx and network errors are temporary ("model overloaded"): retry after 10, 30 and 60 s;
  if that fails, the next provider answers this request. A provider is dropped for the rest
  of the run only after two requests in a row failed that way.
- 401, 403 and 404 (bad key, unknown model) drop the provider at once.
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
TIMEOUT_S = 120
RETRY_WAITS_S = (10, 30, 60)
MAX_OUTPUT_TOKENS = 8192
TRANSIENT = {429, 500, 502, 503, 504, None}
FATAL = {401, 403, 404}
DROP_AFTER = 2  # consecutive failed requests
_SKIP = re.compile(r"lite|image|tts|live|audio|embedding|exp|thinking|vision|guard")


class LlmUnavailable(Exception):
    pass


class LlmBadOutput(Exception):
    """The provider answered, but not with usable JSON."""


class _ProviderError(Exception):
    def __init__(self, message: str, status: int | str | None = None):
        super().__init__(message)
        self.status = status


def _version(name: str) -> tuple[float, ...]:
    m = re.search(r"(\d+(?:\.\d+)?)", name)
    return (float(m.group(1)),) if m else (0.0,)


def pick_model(available: list[str], prefer: list[str], family: str | None) -> str | None:
    """The first preferred model that exists, else the newest stable model of the family."""
    for p in prefer:
        if p in available:
            return p
    pool = [m for m in available if (family is None or family in m) and not _SKIP.search(m)]
    stable = [m for m in pool if "preview" not in m] or pool
    return max(stable, key=_version) if stable else None


@dataclass
class _Provider:
    name: str
    key: str
    rpm: int
    prefer: list[str]
    family: str | None
    model: str | None = None
    last_call: float = 0.0
    dead: bool = False
    failures: int = 0


@dataclass
class LlmClient:
    cfg: dict
    calls: int = 0
    providers: list[_Provider] = field(default_factory=list)
    used: list[str] = field(default_factory=list)

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
        return any(not p.dead for p in self.providers)

    def usage(self) -> dict:
        return {"provider": self.used[-1].split(":")[0] if self.used else None,
                "model": self.used[-1].split(":", 1)[1] if self.used else None,
                "calls": self.calls,
                "fallback_used": len({u.split(":")[0] for u in self.used}) > 1
                or bool(self.used and self.used[0].split(":")[0] != "gemini")}

    def complete_json(self, system: str, user: str) -> str:
        """Raw JSON text from the first provider that answers. Counts one call per request."""
        for p in self.providers:
            if p.dead:
                continue
            try:
                if p.model is None:
                    p.model = self._resolve_model(p)
                text = self._call_with_retry(p, system, user)
            except _ProviderError as e:
                p.failures += 1
                if e.status in FATAL or e.status == "no-model" or p.failures >= DROP_AFTER:
                    p.dead = True
                    log.warning("%s dropped for the rest of the run: %s", p.name, e)
                else:
                    log.warning("%s failed this request, trying the next provider: %s", p.name, e)
                continue
            p.failures = 0
            self.used.append(f"{p.name}:{p.model}")
            return text
        raise LlmUnavailable("no LLM provider answered")

    def _resolve_model(self, p: _Provider) -> str:
        if p.name == "gemini":
            r = self._http("GET", f"{GEMINI}/models", p, params={"pageSize": 1000})
            names = [m["name"].removeprefix("models/") for m in r.json().get("models", [])
                     if "generateContent" in m.get("supportedGenerationMethods", [])]
        else:
            r = self._http("GET", f"{GROQ}/models", p)
            names = [m["id"] for m in r.json().get("data", [])]
        model = pick_model(names, p.prefer, p.family)
        if model is None:
            raise _ProviderError("no suitable model in the provider's model list", "no-model")
        if model not in p.prefer:
            log.warning("%s: preferred models %s not available; using %s", p.name, p.prefer, model)
        log.info("%s model: %s", p.name, model)
        return model

    def _call_with_retry(self, p: _Provider, system: str, user: str) -> str:
        for wait in (*RETRY_WAITS_S, None):
            try:
                return self._call(p, system, user)
            except _ProviderError as e:
                if wait is None or e.status not in TRANSIENT:
                    raise
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
        except httpx.HTTPError as e:
            raise _ProviderError(f"{type(e).__name__}") from e
        if r.status_code != 200:
            # The body can echo the request, so keep only a short, key-free excerpt.
            raise _ProviderError(f"HTTP {r.status_code}: {r.text[:160]}", r.status_code)
        return r
