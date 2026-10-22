"""RSS and Atom feeds."""

import calendar
from datetime import UTC, datetime

import feedparser

from .base import FetchError, FetchResult, RawItem, get


def parse(content: bytes | str) -> list[RawItem]:
    feed = feedparser.parse(content)
    # An HTML bot-check page served with HTTP 200 parses as an empty feed with no version.
    if not feed.version:
        raise FetchError(f"not an RSS or Atom feed: {feed.get('bozo_exception')}")
    items = []
    for e in feed.entries:
        url = e.get("link")
        title = (e.get("title") or "").strip()
        if not url or not title:
            continue
        parsed = e.get("published_parsed") or e.get("updated_parsed")
        published = (datetime.fromtimestamp(calendar.timegm(parsed), tz=UTC)
                     if parsed else None)
        items.append(RawItem(url=url, title=title, published_at=published,
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
    return FetchResult(source_id=source["id"], ok=not errors, items=items,
                       http_status=http_status, error="; ".join(errors) or None)
