"""Backfill the GKG daily counts in baselines.json for days before live counting began, so M and
the theatre activity have their 90-day baseline at once instead of after weeks of warm-up.

python -m pipeline.tools.gkg_backfill FIRST_DAY LAST_DAY OUT.json   count, write OUT.json
python -m pipeline.tools.gkg_backfill --merge OUT.json BASELINES.json   replace those days

Counts one GKG file per hour (24 of the 96 a day, as the replays do) with the live adapter's
count_file and scales each day by 96 / files found, so a sampled day estimates a full day;
files_per_day is 4 x files found, so a day with 23 or 24 hours passes the live 90-file rule.
Merging replaces a day outright (the first live day was only partly counted). About 5 MB is
downloaded per file and nothing but the counts is kept. First run 2026-10-27.
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import yaml

from ..adapters.gdelt_gkg import count_file
from ..store.state import _write
from .gkg_replay import CONFIG, first_file_in_hour


def backfill(first: date, last: date) -> dict:
    src = next(s for s in yaml.safe_load((CONFIG / "sources.yaml").read_text())["sources"]
               if s["adapter"] == "gdelt_gkg")
    cfg = src["gkg"]
    themes, fips, eu = set(cfg["themes"]), cfg["countries"], set(cfg["eu"])
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    stamps = [f"{d:%Y%m%d}{h:02d}0000" for d in days for h in range(24)]

    def one(ts: str):
        raw = first_file_in_hour(ts)
        return ts, None if raw is None else count_file(raw, themes, fips, eu)

    found: dict[str, int] = {}
    counts: dict[str, dict] = {}
    tones: dict[str, dict] = {}
    missing = []
    with ThreadPoolExecutor(8) as pool:
        for n, (ts, got) in enumerate(pool.map(one, stamps), 1):
            day = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
            if got is None:
                missing.append(ts)
                continue
            found[day] = found.get(day, 0) + 1
            # Records are keyed by the file's day, as files_per_day is: an article dated just
            # before midnight in the 00:00 file still belongs to the file's day here.
            for target, part in ((counts, got[0]), (tones, got[1])):
                d = target.setdefault(day, {})
                for themes_ in part.values():
                    for theme, by_country in themes_.items():
                        t = d.setdefault(theme, {})
                        for k, v in by_country.items():
                            t[k] = t.get(k, 0) + v
            if n % 96 == 0:
                print(f"  {n} of {len(stamps)} files", file=sys.stderr)
    for day, n in found.items():
        scale = 96 / n
        for target, kind in ((counts, int), (tones, float)):
            for by_country in target.get(day, {}).values():
                for k, v in by_country.items():
                    by_country[k] = round(v * scale) if kind is int else round(v * scale, 3)
    return {"sampling": "one GKG file per hour, the first that exists; scaled by 96 / found",
            "files_per_day": {d: 4 * n for d, n in sorted(found.items())},
            "missing": missing, "daily": counts, "tone": tones}


def merge(out: dict, baselines: dict) -> dict:
    gkg = baselines["gkg"]
    for day in out["files_per_day"]:
        gkg["files_per_day"][day] = out["files_per_day"][day]
        gkg["daily"][day] = out["daily"].get(day, {})
        gkg.setdefault("tone", {})[day] = out["tone"].get(day, {})
    for key in ("files_per_day", "daily", "tone"):
        gkg[key] = dict(sorted(gkg[key].items()))
    return baselines


def main() -> None:
    if sys.argv[1] == "--merge":
        out, path = json.loads(Path(sys.argv[2]).read_text()), Path(sys.argv[3])
        _write(path, merge(out, json.loads(path.read_text())))  # the pipeline's own format
        print(f"merged {len(out['files_per_day'])} days into {path}", file=sys.stderr)
        return
    out = backfill(date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2]))
    Path(sys.argv[3]).write_text(json.dumps(out, sort_keys=True) + "\n")
    print(f"{len(out['files_per_day'])} days, {len(out['missing'])} hours missing",
          file=sys.stderr)


if __name__ == "__main__":
    main()
