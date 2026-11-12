"""The side-by-side week's acceptance check: python -m monitor.tools.acceptance --state-dir state

Measures the rebuilt pipeline against the targets in the design (section 12) from what it has
recorded on the data branch, and compares its index with the old pipeline's for the same
scoring slots. Reads only. The last target, repeats among incidents, needs a person: it prints
a sample of incidents to read.
"""

import argparse
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pipeline.store import state as old_state

from .. import store

SAMPLE = 50


def share(part: int, whole: int) -> str:
    return f"{part} of {whole}" + (f" ({100 * part / whole:.0f}%)" if whole else "")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m monitor.tools.acceptance")
    p.add_argument("--state-dir", type=Path, default=Path("state"))
    p.add_argument("--days", type=int, default=7)
    args = p.parse_args(argv)
    d = args.state_dir
    now = datetime.now(UTC)
    since = (now - timedelta(days=args.days)).isoformat()
    log = [r for r in store.load_json(d, "log.json", []) if r["at"] >= since]
    if not log:
        print("No runs recorded yet.")
        return 1
    hours = (now - datetime.fromisoformat(log[0]["at"])).total_seconds() / 3600
    print(f"Runs recorded since {log[0]['at']}: {len(log)} in {hours:.0f} hours "
          f"(target: at least 95% of the hours)")
    slots = [r for r in log if r["scored"]]
    print("Scoring slots that were ok:", share(sum(r["overall"] == "ok" for r in slots),
                                               len(slots)), "(target 90%)")
    fresh = [r for r in slots if r["brief_written_at"] and datetime.fromisoformat(r["at"])
             - datetime.fromisoformat(r["brief_written_at"]) < timedelta(hours=24)]
    print("Scoring slots with a brief under 24 hours old:", share(len(fresh), len(slots)))
    for r in slots:
        if r["overall"] != "ok":
            print(f"   {r['scored']} {r['overall']}: {'; '.join(r['reasons'])}")

    articles = store.load_articles(d).values()
    done = [a for a in articles if a.labelled_at]
    quick = [a for a in done if a.labelled_at - a.first_seen <= timedelta(hours=3)]
    print("Articles labelled within 3 hours:", share(len(quick), len(done)), "(target 95%)")
    print("Articles given up:", sum(1 for a in articles if a.given_up),
          "| labelled per model:", {m: sum(1 for a in done if a.labelled_by == m)
                                    for m in sorted({a.labelled_by for a in done})})

    incidents = store.load_incidents(d) or []
    own = [i for i in incidents if not i.seeded_from]
    labelled = {a.id for a in done}
    recent = [i for i in own if any(r.article_id in labelled for r in i.reports)]
    bare = [i for i in recent if not all(r.article_id in labelled or r.published_at
                                         < now - timedelta(days=7) for r in i.reports)]
    print(f"Incidents made by this pipeline: {len(own)}; with a report no model labelled: "
          f"{len(bare)} (target 0)")

    ours = {(r["run_id"], r["region"]): r["index"]
            for r in (store.load_public(d, "history.json") or {"rows": []})["rows"]}
    print("Index against the old pipeline, same slot (target: within 5 points):")
    for r in old_state.load_timeseries(d):
        key = (r["run_id"], r["region"])
        if r["at"] >= log[0]["at"] and key in ours:
            gap = ours[key] - r["index"]
            print(f"   {r['run_id']} {r['region']}: old {r['index']}, new {ours[key]} "
                  f"({gap:+d}){'  <-- over 5' if abs(gap) > 5 else ''}")

    print(f"\nA sample of up to {SAMPLE} incidents to read for repeats (target: at most 2):")
    random.seed(0)
    for i in sorted(random.sample(own, min(SAMPLE, len(own))), key=lambda i: (i.country, i.date)):
        print(f"   {i.date} {i.country} {i.type:16} {len(i.reports):2} reports | {i.title_en[:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
