"""RSS and Atom feeds."""

import calendar
import re
from datetime import UTC, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser

from .base import FetchError, FetchResult, RawItem, get, postfilter

# feedparser reads these abbreviations as UTC; CERT-EU's feeds use them.
_TZ_ABBR = {"CEST": 2, "CET": 1, "EEST": 3, "EET": 2}
_ABBR_AT_END = re.compile(r"\s(CEST|CET|EEST|EET)\s*$")


def _published(entry) -> datetime | None:
    raw = entry.get("published") or entry.get("updated") or ""
    if m := _ABBR_AT_END.search(raw):
        dt = parsedate_to_datetime(raw[: m.start()] + " +0000")
        return dt.replace(tzinfo=timezone(timedelta(hours=_TZ_ABBR[m.group(1)]))).astimezone(UTC)
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    return datetime.fromtimestamp(calendar.timegm(parsed), tz=UTC) if parsed else None


def parse(content: bytes | str) -> list[RawItem]:
    feed = feedparser.parse(content)
    # An HTML bot-check page served with HTTP 200 parses as an empty feed with no version.
    if not feed.version:
        raise FetchError(f"not an RSS or Atom feed: {feed.get('bozo_exception')}")
    items = []
    for e in feed.entries:
        url = (e.get("link") or "").strip()
        title = (e.get("title") or "").strip()
        if not url or not title:
            continue
        items.append(RawItem(url=url, title=title, published_at=_published(e),
                             snippet=e.get("summary") or ""))
    return items


def fetch(source: dict) -> FetchResult:
    """Fetch every URL of a source. One failing URL fails the source but keeps the other items."""
    items: list[RawItem] = []
    errors: list[str] = []
    http_status = None
    for url in source["urls"]:
        try:
            r = get(url)
            http_status = r.status_code
            items.extend(parse(r.content))
        except FetchError as e:
            http_status = e.http_status
            errors.append(f"{url}: {e}")
    return FetchResult(source_id=source["id"], ok=not errors, items=postfilter(items, source),
                       http_status=http_status, error="; ".join(errors) or None)
