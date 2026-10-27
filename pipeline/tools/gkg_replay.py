"""Daily TERROR article counts from GDELT GKG bulk files around past incidents, for replays.

python -m pipeline.tools.gkg_replay [INCIDENT_ID ...]   writes pipeline/data/replays/<id>.json

Downloads one GKG file per hour (the first that exists, usually :00; 24 of the 96 a day)
from 15 days before the incident to 2 days after, counts it in memory with the live adapter's
count_file and keeps only the daily counts. Sampling the same hours every day keeps the ratio
to the median that M uses; the replay test scales counts and files by 4, so the live rule
(90 of 96 files for a complete day) means 23 of these 24. About 2.5 GB is downloaded per
incident; nothing but the counts is stored. Missing hours are listed in the output.
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml

from ..adapters.base import FetchError, get
from ..adapters.gdelt_gkg import BASE, count_file

CONFIG = Path(__file__).parents[1] / "config"
OUT = Path(__file__).parents[1] / "data" / "replays"
THEME = "TERROR"
KEYS = ("SK", "EU", "ALL")
DAYS_BEFORE, DAYS_AFTER = 15, 2

# The incidents in docs/SCORING.md, by the UTC day of the attack.
INCIDENTS = {
    "vienna_2020": date(2020, 11, 2),
    "bratislava_2022": date(2022, 10, 12),
    "solingen_2024": date(2024, 8, 23),
    "villach_2025": date(2025, 2, 15),
}


def hours(day: date) -> list[str]:
    start = datetime(day.year, day.month, day.day, tzinfo=UTC) - timedelta(days=DAYS_BEFORE)
    n = 24 * (DAYS_BEFORE + DAYS_AFTER + 1)
    return [(start + timedelta(hours=h)).strftime("%Y%m%d%H%M%S") for h in range(n)]


def first_file_in_hour(ts: str) -> bytes | None:
    """The hour's first GKG file that exists: GDELT's archive has gaps (in 2020, many :00
    files answer 404 while :15 exists)."""
    for minute in ("00", "15", "30", "45"):
        try:
            return get(f"{BASE}{ts[:10]}{minute}00.gkg.csv.zip", retries=2, backoff_s=5).content
        except FetchError as e:
            if e.http_status == 404:
                continue
            print(f"  {ts}: {e}", file=sys.stderr)
            return None
    print(f"  {ts}: no file in this hour", file=sys.stderr)
    return None


def replay_counts(incident: str) -> dict:
    src = next(s for s in yaml.safe_load((CONFIG / "sources.yaml").read_text())["sources"]
               if s["adapter"] == "gdelt_gkg")
    fips, eu = src["gkg"]["countries"], set(src["gkg"]["eu"])

    def one(ts: str) -> tuple[str, dict | None]:
        raw = first_file_in_hour(ts)
        return ts, None if raw is None else count_file(raw, {THEME}, fips, eu)[0]

    files: dict[str, int] = {}
    counts: dict[str, dict[str, int]] = {}
    missing = []
    with ThreadPoolExecutor(4) as pool:
        for ts, got in pool.map(one, hours(INCIDENTS[incident])):
            day = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
            if got is None:
                missing.append(ts)
                continue
            files[day] = files.get(day, 0) + 1
            row = counts.setdefault(day, dict.fromkeys(KEYS, 0))
            for by_country in (d.get(THEME, {}) for d in got.values()):
                for k in KEYS:
                    row[k] += by_country.get(k, 0)
    return {"incident": incident, "date": INCIDENTS[incident].isoformat(), "theme": THEME,
            "sampling": "one GKG file per hour, the first that exists", "files_per_day": files,
            "missing": missing, "counts": counts}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for incident in sys.argv[1:] or list(INCIDENTS):
        print(f"{incident}: fetching", file=sys.stderr)
        data = replay_counts(incident)
        (OUT / f"{incident}.json").write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
        print(f"{incident}: {sum(data['files_per_day'].values())} files, "
              f"{len(data['missing'])} missing", file=sys.stderr)


if __name__ == "__main__":
    main()
