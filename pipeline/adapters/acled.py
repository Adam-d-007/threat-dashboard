"""ACLED API: political violence and protest events (acleddata.com/api-documentation).

Signs in with the OAuth password grant (ACLED_EMAIL, ACLED_PASSWORD from GitHub secrets),
then reads the last `days` days for the configured regions with cursor pagination
(page= is deprecated from 27 October 2026). ACLED revises past events, so each run replaces
its whole slice. Events are records, not articles: they have no URL of their own.

Written from ACLED's documentation on 2026-10-22, before an account existed to test it;
verify on the first real run.
"""

import os
from datetime import datetime, timedelta

import httpx

from .base import TIMEOUT_S, TLS, USER_AGENT, FetchError, FetchResult, get

TOKEN_URL = "https://acleddata.com/oauth/token"
FIELDS = ("event_id_cnty|event_date|disorder_type|event_type|sub_event_type|actor1|actor2|"
          "country|iso|admin1|location|latitude|longitude|geo_precision|fatalities|source|"
          "notes|timestamp")
MAX_PAGES = 40


def token(email: str, password: str) -> str:
    r = httpx.post(TOKEN_URL, timeout=TIMEOUT_S, verify=TLS, headers={"User-Agent": USER_AGENT},
                   data={"username": email, "password": password, "grant_type": "password",
                         "client_id": "acled", "scope": "authenticated"})
    if r.status_code != 200:
        raise FetchError(f"token request failed: HTTP {r.status_code}", r.status_code)
    return r.json()["access_token"]


def read_events(url: str, bearer: str, region: int, since: str, until: str,
                limit: int = 5000) -> list[dict]:
    events, cursor = [], 0
    for _ in range(MAX_PAGES):
        r = get(url, check_robots=False, headers={"Authorization": f"Bearer {bearer}"},
                params={"_format": "json", "region": region, "event_date": f"{since}|{until}",
                        "event_date_where": "BETWEEN", "fields": FIELDS, "limit": limit,
                        "cursor": cursor})
        body = r.json()
        if not body.get("success", True):
            raise FetchError(f"ACLED error: {body.get('messages') or body.get('error')}")
        events.extend(body.get("data") or [])
        cursor = body.get("next_cursor")
        if cursor is None:
            return events
    raise FetchError(f"more than {MAX_PAGES} pages; raise MAX_PAGES or narrow the query")


def fetch(source: dict, now: datetime) -> FetchResult:
    email, password = os.environ.get("ACLED_EMAIL"), os.environ.get("ACLED_PASSWORD")
    if not email or not password:
        return FetchResult(source_id=source["id"], ok=False,
                           error="ACLED_EMAIL and ACLED_PASSWORD are not set")
    cfg = source["acled"]
    since = (now - timedelta(days=cfg["days"])).strftime("%Y-%m-%d")
    until = now.strftime("%Y-%m-%d")
    try:
        bearer = token(email, password)
        records = [e for region in cfg["regions"]
                   for e in read_events(source["urls"][0], bearer, region, since, until)]
    except (FetchError, httpx.HTTPError, KeyError, ValueError) as e:
        return FetchResult(source_id=source["id"], ok=False, error=f"{type(e).__name__}: {e}",
                           http_status=getattr(e, "http_status", None))
    return FetchResult(source_id=source["id"], ok=True, records=records, http_status=200)
