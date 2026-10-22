"""News lists served as JSON by a site's own front end. Mapping lives in sources.yaml:

  json:
    items: key of the list in the response
    title, link, date, snippet: keys inside each entry
    date_format: strptime format
    base: prefix for relative links
"""

from urllib.parse import urljoin

from .base import FetchError, FetchResult, RawItem, get, postfilter
from .dates import parse_listed


def parse(data: dict, cfg: dict) -> list[RawItem]:
    entries = data.get(cfg["items"])
    if not isinstance(entries, list) or not entries:
        raise FetchError(f"no list at {cfg['items']!r}")
    items = []
    for e in entries:
        if not e.get(cfg["title"]) or not e.get(cfg["link"]) or not e.get(cfg["date"]):
            continue
        try:
            published, date_only = parse_listed(e[cfg["date"]], cfg["date_format"],
                                                cfg.get("tz", "UTC"))
        except ValueError as err:
            raise FetchError(f"date {e[cfg['date']]!r} does not match "
                             f"{cfg['date_format']!r}") from err
        items.append(RawItem(url=urljoin(cfg["base"], e[cfg["link"]]),
                             title=e[cfg["title"]].strip(), published_at=published,
                             snippet=e.get(cfg.get("snippet", ""), "") or "",
                             date_only=date_only))
    return items


def fetch(source: dict) -> FetchResult:
    try:
        r = get(source["urls"][0])
        items = parse(r.json(), source["json"])
    except (FetchError, ValueError) as e:
        return FetchResult(source_id=source["id"], ok=False,
                           http_status=getattr(e, "http_status", None), error=str(e))
    return FetchResult(source_id=source["id"], ok=True, items=postfilter(items, source),
                       http_status=r.status_code)
