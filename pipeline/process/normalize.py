"""Turn adapter output into Items: canonical URL, UTC times, short plain-text snippet."""

import hashlib
import html
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit, urlunsplit

from ..adapters.base import RawItem
from ..models import Item

SNIPPET_MAX = 300
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def canonical_url(url: str) -> str:
    """Lowercase scheme and host; drop utm_* and amp parameters, AMP paths, fragments and
    trailing slashes. Every other query parameter is kept exactly as written: some sites
    (minv.sk/?tlacove-spravy&sprava=...) route on a bare key, and re-encoding it as
    "tlacove-spravy=" opens their homepage instead of the article."""
    parts = urlsplit(url.strip())
    kept = [p for p in parts.query.split("&")
            if p and not p.split("=", 1)[0].lower().startswith("utm_")
            and p.split("=", 1)[0].lower() != "amp"]
    path = re.sub(r"(/amp)+(?=/|$)", "", parts.path)
    if path.endswith(".amp"):
        path = path[:-4]
    path = path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "&".join(kept), ""))


def item_id(canonical: str) -> str:
    return hashlib.sha1(canonical.encode()).hexdigest()


def clean_text(text: str, limit: int = SNIPPET_MAX) -> str:
    text = _SPACE.sub(" ", html.unescape(_TAG.sub(" ", text))).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def domain_of(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def normalize(raw: RawItem, source: dict, fetched_at: datetime,
              first_seen: dict[str, str]) -> Item:
    """Build an Item. first_seen maps item id to the first time the pipeline saw it; it dates
    items whose source gives no date, or a date without a time."""
    url = canonical_url(raw.url)
    iid = item_id(url)
    seen_at = datetime.fromisoformat(first_seen.get(iid, fetched_at.isoformat()))
    estimated = raw.published_at is None or raw.date_only
    if raw.published_at is None:
        published = seen_at
    elif raw.date_only:
        # A day without a time. Midnight would put a morning item before the window of the
        # afternoon run and lose it, so use the first sighting on that day, else midday.
        day_start = raw.published_at.astimezone(UTC)
        same_day = timedelta(0) <= seen_at - day_start < timedelta(days=1)
        published = seen_at if same_day else day_start + timedelta(hours=12)
    else:
        published = raw.published_at.astimezone(UTC)
    lang = raw.lang or source["lang"]
    return Item(
        id=iid, source_id=source["id"], tier=source["tier"], url=url,
        title=clean_text(raw.title, 500), lang=lang if lang != "multi" else "und",
        published_at=published, published_estimated=estimated, fetched_at=fetched_at,
        snippet=clean_text(raw.snippet), domain=raw.domain or domain_of(url),
    )
