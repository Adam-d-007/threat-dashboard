"""Rebuild step 3 check, run once by hand: python -m monitor.tools.replay --state-dir state

Takes the stories the old pipeline split into many "incidents" (the Kraków shooting and its
follow-ups, the school bomb hoaxes, the Nvidia affair, the US soldier arrested in Britain),
sends their stored articles through the new labelling and matching from an empty incident
list, and prints how many incidents each story becomes. Reads the old pipeline's stored runs;
writes nothing. Needs GEMINI_API_KEY and/or GROQ_API_KEY.
"""

import argparse
import json
import logging
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from pipeline.models import Item

from .. import settings
from ..ai.client import Ai
from ..incidents import match
from ..labelling import label
from ..models import Article

STORIES = {
    "Kraków shooting": r"Krak",
    "school bomb hoaxes": r"(?i)school",
    "Nvidia affair": r"Nvidia",
    "US soldier arrested in Britain": r"(?i)US (soldier|army)|army member",
}
PER_EVENT = 6   # articles taken from each old event, oldest first


def stories(state_dir: Path) -> dict[str, list[Item]]:
    """Per story: stored articles of every old event whose title names it."""
    items: dict[str, dict] = {}
    for path in sorted((state_dir / "runs").glob("2*.json")):
        for i in json.loads(path.read_text())["items"]:
            items.setdefault(i["id"], i)
    events = json.loads((state_dir / "latest.json").read_text())["events"]
    out = {}
    for name, pattern in STORIES.items():
        mine = [e for e in events if re.search(pattern, e["title_en"])]
        found = {}
        for e in mine:
            have = sorted((items[i] for i in e["item_ids"] if i in items),
                          key=lambda i: i["published_at"])[:PER_EVENT]
            found |= {i["id"]: Item.model_validate(i) for i in have}
        out[name] = list(found.values())
        print(f"{name}: {len(mine)} old events, {len(found)} stored articles taken")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m monitor.tools.replay")
    p.add_argument("--state-dir", type=Path, default=Path("state"))
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    cfg = settings.load()
    story_of: dict[str, str] = {}
    articles: dict[str, Article] = {}
    for name, items in stories(args.state_dir).items():
        for i in items:
            story_of.setdefault(i.id, name)
            articles[i.id] = Article(
                **i.model_dump(include={"id", "source_id", "tier", "url", "title", "lang",
                                        "published_at", "fetched_at", "snippet", "domain",
                                        "also_reported_by"}), first_seen=i.published_at)
    now = datetime.now(UTC).replace(microsecond=0)
    ai = Ai.from_env(cfg["ai"])
    long = {"max_seconds": 1500, "max_age_hours": 24 * 60}
    print("labelling:", label(articles, ai, cfg["label"] | long, now))
    incidents: list = []
    print("matching:", match(articles, incidents, ai, cfg["match"] | long, now))

    kinds = Counter((story_of[a.id], a.label.kind if a.label else "unlabelled")
                    for a in articles.values())
    print("\nRESULT")
    for name in STORIES:
        mine = [i for i in incidents
                if Counter(story_of[r.article_id] for r in i.reports).most_common(1)[0][0] == name]
        print(f"\n{name}: {len(mine)} incidents; labels "
              f"{ {k: n for (s, k), n in sorted(kinds.items()) if s == name} }")
        for i in sorted(mine, key=lambda i: i.date):
            print(f"  {i.id} {i.date} {i.country} {i.type} severity {i.severity}, "
                  f"{len(i.reports)} reports | {i.title_en[:100]}")
            for r in i.reports:
                print(f"      {r.published_at:%m-%d %H:%M} {r.kind:12} {r.source:22} "
                      f"{(r.summary_en or '')[:90]}")
    print("\nAI use:", json.dumps(ai.report()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
