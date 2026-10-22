"""Shared adapter types and the HTTP client every adapter uses."""

import time
from dataclasses import dataclass, field
from datetime import datetime

import httpx

USER_AGENT = "threat-dashboard/0.1 (+https://github.com/Adam-d-007/threat-dashboard)"
TIMEOUT_S = 30
RETRIES = 2
BACKOFF_S = 2.0


@dataclass
class RawItem:
    """An item as an adapter found it, before normalization."""

    url: str
    title: str
    published_at: datetime | None  # timezone-aware, or None when the source gives no date
    snippet: str = ""
    lang: str | None = None
    domain: str | None = None


@dataclass
class FetchResult:
    source_id: str
    ok: bool
    items: list[RawItem] = field(default_factory=list)
    http_status: int | None = None
    error: str | None = None


class FetchError(Exception):
    def __init__(self, message: str, http_status: int | None = None):
        super().__init__(message)
        self.http_status = http_status


def get(url: str, params: dict | None = None, retries: int = RETRIES,
        backoff_s: float = BACKOFF_S) -> httpx.Response:
    """GET with a 30 s timeout and exponential backoff on network errors, 429 and 5xx.

    Raises FetchError when every attempt fails or the server answers another 4xx.
    """
    last: FetchError | None = None
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(backoff_s * 2 ** (attempt - 1))
        try:
            r = httpx.get(url, params=params, timeout=TIMEOUT_S, follow_redirects=True,
                          headers={"User-Agent": USER_AGENT})
        except httpx.HTTPError as e:
            last = FetchError(f"{type(e).__name__}: {e}")
            continue
        if r.status_code == 200:
            return r
        last = FetchError(f"HTTP {r.status_code}", r.status_code)
        if r.status_code != 429 and r.status_code < 500:
            break
    assert last is not None
    raise last
