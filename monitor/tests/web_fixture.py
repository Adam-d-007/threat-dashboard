"""Write the v2 files the website's tests read: python -m monitor.tests.web_fixture OUT_DIR

One hourly run of the real code on the small made-up state of test_run.py, with its rule-based
stand-in for the models, so the website is tested against files this pipeline really writes:
a Kraków incident with a follow-up on its timeline, one incident carried over from the old
pipeline, three labelled reports, a scored summary and a brief for one theatre.
"""

import shutil
import sys
import tempfile
from pathlib import Path

from monitor import run
from monitor.tests.test_run import AT, RuleAi, build_state

FILES = {"status.json": "status.json", "summary.json": "summary.json",
         "incidents/current.json": "incidents.json", "reports.json": "reports.json",
         "geopolitics.json": "geopolitics.json", "history.json": "history.json"}


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    run.Ai = RuleAi
    with tempfile.TemporaryDirectory() as tmp:
        state = build_state(Path(tmp))
        code = run.main(["--state-dir", str(state), "--git-sha", "fixture", "--now",
                         AT.isoformat()])
        assert code == 0
        for name, flat in FILES.items():
            shutil.copy(state / "v2" / name, out / flat)


if __name__ == "__main__":
    main()
