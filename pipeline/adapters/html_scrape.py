"""News lists on pages without a feed. Selectors live in sources.yaml under html:

  html:
    item: CSS selector for one list entry
    title: CSS selector (inside item) for the title text
    link: CSS selector (inside item) for the element with href; "self" for the item itself
    date: CSS selector (inside item) for the date element
    date_attr: optional attribute holding the date (e.g. datetime); default the text
    date_format: strptime format, or "iso"
    tz: time zone of dates without an offset (default UTC)
"""

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import FetchError, FetchResult, RawItem, get, postfilter
from .dates import parse_listed


def parse(html: str, base_url: str, cfg: dict) -> list[RawItem]:
    soup = BeautifulSoup(html, "html.parser")
    entries = soup.select(cfg["item"])
    if not entries:
        # A changed layout or a bot wall: fail loudly instead of reporting an empty list.
        title = soup.title.get_text(strip=True) if soup.title else ""
        raise FetchError(f"no items match {cfg['item']!r} (page title {title!r})")
    items, seen = [], set()
    for el in entries:
        t = el.select_one(cfg["title"])
        a = el if cfg["link"] == "self" else el.select_one(cfg["link"])
        d = el.select_one(cfg["date"])
        if not (t and a and a.get("href") and d):
            continue
        url = urljoin(base_url, a["href"].strip())
        if url in seen:
            continue
        seen.add(url)
        raw = d.get(cfg["date_attr"]) if cfg.get("date_attr") else d.get_text(" ", strip=True)
        try:
            published, date_only = parse_listed(raw or "", cfg["date_format"], cfg.get("tz", "UTC"))
        except ValueError as e:
            raise FetchError(f"date {raw!r} does not match {cfg['date_format']!r}") from e
        items.append(RawItem(url=url, title=t.get_text(" ", strip=True), published_at=published,
                             date_only=date_only))
    if not items:
        raise FetchError(f"{len(entries)} entries matched but none had title, link and date")
    return items


def fetch(source: dict) -> FetchResult:
    url = source["urls"][0]
    try:
        r = get(url)
        r.encoding = r.encoding or "utf-8"
        items = parse(r.text, str(r.url), source["html"])
    except FetchError as e:
        return FetchResult(source_id=source["id"], ok=False, http_status=e.http_status,
                           error=str(e))
    return FetchResult(source_id=source["id"], ok=True, items=postfilter(items, source),
                       http_status=r.status_code)
