"""Recompute events_raw in timeseries.json from the current events.json and scoring rules, so the
events baseline (the median E is compared with) follows a corrected method instead of keeping
what the old method counted. Each run only sees events first seen by its time.

python -m pipeline.tools.rescore_events_history STATE_DIR

Run after a pipeline run with the new rules has cleaned events.json. First used 2026-10-27,
when unrest stopped counting and follow-up reports stopped making new attacks. The published
index and level of each run are left as they were.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

from ..models import Event
from ..score.components import event_contributions
from ..store.state import load_timeseries, write_timeseries

CONFIG = Path(__file__).parents[1] / "config"


def rescore(rows: list[dict], events: list[Event], cfg: dict) -> int:
    changed = 0
    for r in rows:
        if r.get("components", {}).get("events_raw") is None:
            continue
        at = datetime.fromisoformat(r["at"])
        seen = [e for e in events if e.first_seen <= at]
        raw = round(sum(w for _, w in event_contributions(seen, r["region"], at, cfg)), 3)
        if raw != r["components"]["events_raw"]:
            r["components"]["events_raw"] = raw
            changed += 1
    return changed


def main() -> None:
    state = Path(sys.argv[1])
    cfg = yaml.safe_load((CONFIG / "scoring.yaml").read_text())
    events = [Event.model_validate(e)
              for e in json.loads((state / "events.json").read_text())["events"]]
    rows = load_timeseries(state)
    changed = rescore(rows, events, cfg)
    write_timeseries(state, rows)
    print(f"events_raw recomputed: {changed} of {len(rows)} rows changed", file=sys.stderr)


if __name__ == "__main__":
    main()
