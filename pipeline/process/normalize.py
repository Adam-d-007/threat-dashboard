"""Turn adapter output into Items: canonical URL, UTC times, short plain-text snippet."""

import hashlib
import html
import re
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..adapters.base import RawItem
from ..models import Item

SNIPPET_MAX = 300
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def canonical_url(url: str) -> str:
    """Lowercase scheme and host; drop utm_* parameters, AMP paths, fragments, trailing slashes."""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() != "amp"]
    path = re.sub(r"(/amp)+(?=/|$)", "", parts.path)
    if path.endswith(".amp"):
        path = path[:-4]
    path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


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
    """Build an Item. first_seen maps item id to the first time the pipeline saw it,
    and dates items whose source gives none."""
    url = canonical_url(raw.url)
    iid = item_id(url)
    estimated = raw.published_at is None
    if estimated:
        published = datetime.fromisoformat(first_seen.get(iid, fetched_at.isoformat()))
    else:
        published = raw.published_at.astimezone(UTC)
    lang = raw.lang or source["lang"]
    return Item(
        id=iid, source_id=source["id"], tier=source["tier"], url=url,
        title=clean_text(raw.title, 500), lang=lang if lang != "multi" else "und",
        published_at=published, published_estimated=estimated, fetched_at=fetched_at,
        snippet=clean_text(raw.snippet), domain=raw.domain or domain_of(url),
    )
