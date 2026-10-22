"""Open, update or close GitHub issues after a pipeline run. Standard library only.

Usage: alerts.py STATE_DIR JOB_STATUS   (run in the workflow with GH_TOKEN set)

- pipeline-failure: opened when the job failed or the last two runs were partial. While it is
  open, only a hard failure adds a comment (partial runs are common while GDELT rate-limits
  GitHub's servers, and every comment is an email). The next ok run comments and closes it.
- sis-change: opened when the SIS level or the wording of its level paragraph changed.
GitHub emails the repository owner about new issues and comments.
"""

import json
import subprocess
import sys
from pathlib import Path

FAILURE = "pipeline-failure"
SIS = "sis-change"


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def open_issue(label: str) -> str | None:
    out = gh("issue", "list", "--label", label, "--state", "open", "--json", "number",
             "--jq", ".[0].number")
    return out.strip() or None


def ensure_label(label: str, color: str, description: str) -> None:
    gh("label", "create", label, "--color", color, "--description", description, "--force")


def main() -> None:
    state, job = Path(sys.argv[1]), sys.argv[2]
    # runs/ also holds index.json (the run picker's list), which is not a run.
    runs = sorted(p for p in (state / "runs").glob("*.json") if p.name != "index.json")
    last = [json.loads(p.read_text())["run"] for p in runs[-2:]]
    latest = json.loads((state / "latest.json").read_text()) if (state / "latest.json").exists() \
        else {}
    run = latest.get("run", {})
    ensure_label(FAILURE, "d03b3b", "A pipeline run failed or two runs in a row were partial")
    ensure_label(SIS, "fab219", "The SIS threat level page changed")

    failed = job != "success"
    two_partial = len(last) == 2 and all(r["status"] == "partial" for r in last)
    issue = open_issue(FAILURE)
    if failed or two_partial:
        what = (f"The workflow job ended with status `{job}`." if failed else
                f"Runs {last[0]['id']} and {last[1]['id']} were both partial.")
        failing = [f"- {s['name']}: {s['status']} ({s.get('error') or 'no error text'})"
                   for s in latest.get("sources", []) if s["status"] in ("failed", "stale")]
        body = (f"{what}\n\nLatest run: `{run.get('id')}`, status `{run.get('status')}`, "
                f"LLM `{(run.get('llm') or {}).get('status')}`.\n\nSources not ok:\n"
                + ("\n".join(failing) or "- none") + "\n\nSee docs/RUNBOOK.md.")
        if issue:
            if failed:
                gh("issue", "comment", issue, "--body", body)
        else:
            gh("issue", "create", "--label", FAILURE, "--title",
               "Pipeline needs attention", "--body", body)
    elif issue and run.get("status") == "ok":
        gh("issue", "comment", issue, "--body", f"Recovered: run `{run['id']}` was ok.")
        gh("issue", "close", issue)

    changes = [c for c in (latest.get("diff") or {}).get("anchor_changes", [])
               if c["id"] == "anchor_sk_sis"]
    if changes and run.get("status") != "failed":
        c = changes[0]
        body = (f"Run `{run.get('id')}` saw a change on the SIS NBAC page: "
                f"`{c['value_from']}` → `{c['value_to']}`.\n\n"
                "Check https://www.sis.gov.sk/o-nas/nbac-sto.html. If the official level "
                "changed, the dashboard already shows it; if only the wording changed, check that "
                "the parser still reads the right sentence (pipeline/anchors.py).")
        gh("issue", "create", "--label", SIS, "--title", "SIS threat level page changed",
           "--body", body)


if __name__ == "__main__":
    main()
