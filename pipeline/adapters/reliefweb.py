"""ReliefWeb API v2 reports (apidoc.reliefweb.int). Needs an approved appname, read from the
RELIEFWEB_APPNAME Actions variable; an unapproved name gets HTTP 403.

Written from ReliefWeb's documentation on 2026-10-22, before the appname was approved;
verify on the first real run.
"""

import os
from datetime import UTC, datetime

import httpx

from .base import TIMEOUT_S, TLS, USER_AGENT, FetchResult, RawItem, postfilter


def parse(body: dict) -> list[RawItem]:
    items = []
    for entry in body.get("data") or []:
        f = entry.get("fields") or {}
        if not f.get("title") or not f.get("url"):
            continue
        created = (f.get("date") or {}).get("created")
        published = datetime.fromisoformat(created).astimezone(UTC) if created else None
        sources = ", ".join(s.get("name", "") for s in f.get("source") or [])
        country = (f.get("primary_country") or {}).get("name", "")
        items.append(RawItem(url=f["url"], title=f["title"].strip(), published_at=published,
                             snippet=" · ".join(x for x in (country, sources) if x),
                             domain="reliefweb.int"))
    return items


def fetch(source: dict, since: datetime) -> FetchResult:
    appname = os.environ.get("RELIEFWEB_APPNAME")
    if not appname:
        return FetchResult(source_id=source["id"], ok=False,
                           error="RELIEFWEB_APPNAME is not set (waiting for approval)")
    cfg = source["reliefweb"]
    query = {
        "profile": "list",
        "fields": {"include": ["title", "url", "date.created", "primary_country.name",
                               "primary_country.iso3", "source.name"]},
        "filter": {"operator": "AND", "conditions": [
            # Only this form is accepted: no microseconds, no "Z" (checked 2026-10-23).
            {"field": "date.created", "value": {"from": since.astimezone(UTC).replace(
                microsecond=0).isoformat()}},
            {"field": "primary_country.iso3", "operator": "OR", "value": cfg["countries"]},
        ]},
        "sort": ["date.created:desc"],
        "limit": cfg["limit"],
    }
    try:
        r = httpx.post(source["urls"][0], params={"appname": appname}, json=query,
                       timeout=TIMEOUT_S, verify=TLS, headers={"User-Agent": USER_AGENT})
    except httpx.HTTPError as e:
        return FetchResult(source_id=source["id"], ok=False, error=f"{type(e).__name__}: {e}")
    if r.status_code != 200:
        return FetchResult(source_id=source["id"], ok=False, http_status=r.status_code,
                           error=f"HTTP {r.status_code}: {r.text[:200]}")
    return FetchResult(source_id=source["id"], ok=True, http_status=200,
                       items=postfilter(parse(r.json()), source))
