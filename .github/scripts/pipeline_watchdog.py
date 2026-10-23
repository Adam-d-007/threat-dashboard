"""Start the pipeline when a run slot is overdue. Standard library only.

Usage: pipeline_watchdog.py   (run by the hourly collector, with GH_TOKEN set)

GitHub runs scheduled workflows late or not at all under load: on 2026-10-23 the 04:05 slot
started at 09:16. After each collector run this checks the current slot (04:05 or 13:05 UTC);
if it is more than 20 minutes old and no pipeline run has started since, it starts one as a
slot run. Any run since the slot started counts, failed ones too, so a failing pipeline is not
restarted every hour.
"""

import json
import subprocess
from datetime import UTC, datetime, timedelta

SLOTS = {"04": (4, 5), "13": (13, 5)}
GRACE = timedelta(minutes=20)


def slot_start(now: datetime) -> datetime:
    h, m = SLOTS["13" if now.hour >= 13 else "04"]
    return now.replace(hour=h, minute=m, second=0, microsecond=0)


def overdue(now: datetime, run_starts: list[datetime]) -> bool:
    start = slot_start(now)
    return now >= start + GRACE and not any(t >= start for t in run_starts)


def main() -> None:
    now = datetime.now(UTC)
    out = subprocess.run(["gh", "run", "list", "--workflow", "pipeline.yml", "--limit", "20",
                          "--json", "createdAt"], check=True, capture_output=True, text=True)
    starts = [datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00"))
              for r in json.loads(out.stdout)]
    if not overdue(now, starts):
        print(f"slot from {slot_start(now):%H:%M} UTC: nothing to do")
        return
    subprocess.run(["gh", "workflow", "run", "pipeline.yml", "--ref", "main",
                    "-f", "slot_run=true"], check=True)
    print(f"slot from {slot_start(now):%H:%M} UTC had no run: pipeline started")


if __name__ == "__main__":
    main()
