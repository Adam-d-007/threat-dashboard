"""GDELT DOC 2.0 API, ArtList mode. Calls run one at a time, at least 5 s apart."""

import json
import time
from datetime import UTC, datetime

from .base import FetchError, FetchResult, RawItem, get

MIN_SPACING_S = 5.5
# GitHub runners share IPs with other GDELT users, so 429s are common: back off 20, 40, 80 s.
RETRIES = 3
BACKOFF_S = 20.0
_last_call = 0.0

# GDELT reports languages by English name.
LANGS = {
    "English": "en", "Slovak": "sk", "Czech": "cs", "German": "de", "Hungarian": "hu",
    "Polish": "pl", "French": "fr", "Ukrainian": "uk", "Russian": "ru", "Italian": "it",
    "Spanish": "es", "Dutch": "nl", "Romanian": "ro", "Slovenian": "sl", "Croatian": "hr",
}


def _call(params: dict, url: str) -> dict:
    global _last_call
    wait = _last_call + MIN_SPACING_S - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    try:
        r = get(url, params=params, retries=RETRIES, backoff_s=BACKOFF_S)
    finally:
        _last_call = time.monotonic()
    try:
        return json.loads(r.text) if r.text.strip() else {}
    except json.JSONDecodeError as e:
        # GDELT answers some bad queries with HTTP 200 and a plain-text message.
        raise FetchError(f"not JSON: {r.text[:200]!r}", r.status_code) from e


def parse(data: dict) -> list[RawItem]:
    items = []
    for a in data.get("articles", []):
        if not a.get("url") or not a.get("title"):
            continue
        seen = datetime.strptime(a["seendate"], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        items.append(RawItem(url=a["url"], title=a["title"].strip(), published_at=seen,
                             lang=LANGS.get(a.get("language", ""), "und"),
                             domain=a.get("domain")))
    return items


def fetch(source: dict, queries: list[dict], since: datetime, until: datetime) -> FetchResult:
    items: list[RawItem] = []
    errors: list[str] = []
    http_status = None
    for q in queries:
        params = {
            "query": q["query"], "mode": "ArtList", "format": "json", "sort": "DateDesc",
            "maxrecords": 250,
            "startdatetime": since.strftime("%Y%m%d%H%M%S"),
            "enddatetime": until.strftime("%Y%m%d%H%M%S"),
        }
        try:
            data = _call(params, source["urls"][0])
            http_status = 200
            items.extend(parse(data))
        except FetchError as e:
            http_status = e.http_status
            errors.append(f"{q['id']}: {e}")
    return FetchResult(source_id=source["id"], ok=not errors, items=items,
                       http_status=http_status, error="; ".join(errors) or None)
