"""Shared adapter types and the HTTP client every adapter uses."""

import re
import ssl
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import certifi
import httpx

USER_AGENT = "threat-dashboard/0.1 (+https://github.com/Adam-d-007/threat-dashboard)"
TIMEOUT_S = 30
RETRIES = 2
BACKOFF_S = 2.0

# certifi's roots plus intermediates that some official sites (SIS, OCAM) fail to send.
TLS = ssl.create_default_context(cafile=certifi.where())
TLS.load_verify_locations(cafile=str(Path(__file__).parents[1] / "certs" / "intermediates.pem"))


@dataclass
class RawItem:
    """An item as an adapter found it, before normalization."""

    url: str
    title: str
    published_at: datetime | None  # timezone-aware, or None when the source gives no date
    snippet: str = ""
    lang: str | None = None
    domain: str | None = None
    date_only: bool = False  # the source gives a day but no time


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


_robots: dict[str, RobotFileParser | None] = {}
_robots_lock = threading.Lock()


def robots_allowed(url: str) -> bool:
    """Whether robots.txt lets our User-Agent fetch url. Cached per host for the run.

    Follows RFC 9309: a 4xx robots.txt (missing, or blocked by a bot wall) allows everything;
    a 5xx or network error means robots.txt is unreachable, which counts as disallowed.
    """
    parts = urlsplit(url)
    host = f"{parts.scheme}://{parts.netloc}"
    with _robots_lock:
        if host not in _robots:
            try:
                r = httpx.get(f"{host}/robots.txt", timeout=TIMEOUT_S, follow_redirects=True,
                              headers={"User-Agent": USER_AGENT}, verify=TLS)
            except httpx.HTTPError as e:
                raise FetchError(f"robots.txt unreachable: {type(e).__name__}") from e
            if r.status_code >= 500:
                raise FetchError(f"robots.txt unreachable: HTTP {r.status_code}", r.status_code)
            if r.status_code >= 400:
                _robots[host] = None
            else:
                rp = RobotFileParser()
                rp.parse(r.text.splitlines())
                _robots[host] = rp
        rp = _robots[host]
    return rp is None or rp.can_fetch(USER_AGENT, url)


def get(url: str, params: dict | None = None, retries: int = RETRIES,
        backoff_s: float = BACKOFF_S, check_robots: bool = True) -> httpx.Response:
    """GET with a 30 s timeout and exponential backoff on network errors, 429 and 5xx.

    Raises FetchError when robots.txt disallows the URL, every attempt fails, or the server
    answers another 4xx.
    """
    if check_robots and not robots_allowed(url):
        raise FetchError("disallowed by robots.txt")
    last: FetchError | None = None
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(backoff_s * 2 ** (attempt - 1))
        try:
            r = httpx.get(url, params=params, timeout=TIMEOUT_S, follow_redirects=True,
                          headers={"User-Agent": USER_AGENT}, verify=TLS)
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


def postfilter(items: list[RawItem], source: dict) -> list[RawItem]:
    """Per-source options from sources.yaml: exclude_title (regex, e.g. paid ads) and
    max_items (keep only the newest, for feeds that carry their whole archive)."""
    if pattern := source.get("exclude_title"):
        rx = re.compile(pattern)
        items = [i for i in items if not rx.search(i.title)]
    if limit := source.get("max_items"):
        newest = sorted(items, key=lambda i: i.published_at.timestamp() if i.published_at else 0,
                        reverse=True)
        items = newest[:limit]
    return items
