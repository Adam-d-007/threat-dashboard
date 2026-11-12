"""Open or close the one GitHub issue about the rebuilt pipeline: python -m monitor.alerts STATE

Opened when no run has been ok for status.alert_after_hours (24); closed by the next ok run.
While open it gets no further comments, so a long outage is one email, not one an hour.
Run in the workflow with GH_TOKEN set. Not called while the old pipeline still runs beside
this one: its own alerts cover the live site until switch-over.
"""

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import settings, store
from .status import alert_due

LABEL = "monitor-failure"


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def main() -> None:
    state_dir = Path(sys.argv[1])
    hours = settings.load()["status"]["alert_after_hours"]
    log = store.load_json(state_dir, "log.json", [])
    last = log[-1] if log else None
    open_issue = gh("issue", "list", "--label", LABEL, "--state", "open", "--json", "number",
                    "--jq", ".[0].number").strip()
    if alert_due(log, datetime.now(UTC), hours) and not open_issue:
        gh("label", "create", LABEL, "--color", "d03b3b", "--force", "--description",
           f"No run of the pipeline has been ok for {hours} hours")
        reasons = "\n".join(f"- {r}" for r in last["reasons"]) or "- none recorded"
        gh("issue", "create", "--label", LABEL, "--title", "Pipeline needs attention", "--body",
           f"No run has been ok for {hours} hours. The latest, at {last['at']}, was "
           f"`{last['overall']}`:\n\n{reasons}\n\nSee docs/RUNBOOK.md.")
    elif open_issue and last and last["overall"] == "ok":
        gh("issue", "comment", open_issue, "--body", f"Recovered: the run at {last['at']} was ok.")
        gh("issue", "close", open_issue)


if __name__ == "__main__":
    main()
