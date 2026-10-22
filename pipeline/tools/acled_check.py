"""Which ACLED data can this account read? python -m pipeline.tools.acled_check

Signs in with ACLED_EMAIL / ACLED_PASSWORD (never printed), then asks for one event from the
last 30 days and one from 13 months ago, both for Europe. Recent data means Partner or
Enterprise access; only old data means Research (12-month lag); neither means no event access.
Also prints ACLED's own data_query_restrictions field from the response.
"""

import json
import os
import sys
from datetime import UTC, datetime, timedelta

from ..adapters.acled import FIELDS, TOKEN_URL, token
from ..adapters.base import FetchError, get

READ_URL = "https://acleddata.com/api/acled/read"


def probe(bearer: str, since: datetime, until: datetime) -> tuple[int, dict]:
    r = get(READ_URL, check_robots=False, headers={"Authorization": f"Bearer {bearer}"},
            params={"_format": "json", "region": 12, "limit": 1, "fields": FIELDS,
                    "event_date": f"{since:%Y-%m-%d}|{until:%Y-%m-%d}",
                    "event_date_where": "BETWEEN"})
    body = r.json()
    return len(body.get("data") or []), {k: v for k, v in body.items() if k != "data"}


def main() -> int:
    email, password = os.environ.get("ACLED_EMAIL"), os.environ.get("ACLED_PASSWORD")
    if not email or not password:
        print("ACLED_EMAIL and ACLED_PASSWORD are not set")
        return 1
    try:
        bearer = token(email, password)
    except FetchError as e:
        print(f"Sign-in failed at {TOKEN_URL}: {e} (wrong email or password, or the account "
              "is not activated yet)")
        return 1
    print("Sign-in OK")
    now = datetime.now(UTC)
    results = {}
    for label, since, until in (("recent (last 30 days)", now - timedelta(days=30), now),
                                ("old (13 to 14 months ago)", now - timedelta(days=425),
                                 now - timedelta(days=395))):
        try:
            n, meta = probe(bearer, since, until)
        except FetchError as e:
            n, meta = 0, {"error": str(e), "http_status": e.http_status}
        results[label] = n
        print(f"\n{label}: {'events returned' if n else 'no events'}")
        print(json.dumps(meta, indent=2, ensure_ascii=False)[:1500])
    recent, old = results.values()
    verdict = ("Partner or Enterprise: recent events available, the adapter can be switched on."
               if recent else
               "Research tier: only data older than 12 months. ACLED can serve base rates only."
               if old else
               "No event-level access (Open tier or API not enabled for this account).")
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
