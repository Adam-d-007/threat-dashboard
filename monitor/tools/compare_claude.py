"""Haiku against Opus on real articles, run once by hand: python -m monitor.tools.compare_claude

Takes the 48 newest labelled articles from the article store, labels them again with Claude
Haiku 5.5 and with Claude Opus 5.5 (six batches of eight each), and prints where the two agree,
where Haiku differs from Opus, and what each cost. Opus is the reference: if Haiku agrees with
it on the kind of report and the incident facts for nearly every article, Haiku labels. Reads
the data branch checkout; writes nothing. Needs ANTHROPIC_API_KEY; costs well under a dollar.
"""

import argparse
import json
from pathlib import Path

from .. import settings, store
from ..ai.client import Ai, AiUnavailable
from ..ai.labels import BATCH_SCHEMA, LABEL_SYSTEM, label_user
from ..labelling import _parse, rows_of

ARTICLES = 48
FIELDS = ("kind", "domain", "incident_type", "severity", "incident_date", "incident_country",
          "sk_link")


def short(x: dict) -> str:
    return (f"{x['kind']} {x['domain']} {x['incident_type']} s{x['severity']} "
            f"{x['incident_date']} {x['incident_country']}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m monitor.tools.compare_claude")
    p.add_argument("--state-dir", type=Path, default=Path("state"))
    args = p.parse_args(argv)

    cfg = settings.load()["ai"]
    ai = Ai.from_env(cfg)
    if "anthropic" not in ai.keys:
        print("ANTHROPIC_API_KEY is not set")
        return 1
    done = [a for a in store.load_articles(args.state_dir).values() if a.label]
    articles = sorted(done, key=lambda a: a.published_at, reverse=True)[:ARTICLES]
    size = settings.load()["label"]["batch_size"]
    batches = [articles[k:k + size] for k in range(0, len(articles), size)]
    labels: dict[str, dict[str, dict]] = {"haiku_55": {}, "opus_55": {}}
    for name in labels:
        cfg["tasks"]["label"]["models"] = [name]
        for batch in batches:
            ids = {str(n) for n in range(1, len(batch) + 1)}
            try:
                got, _ = ai.ask("label", LABEL_SYSTEM, label_user(rows_of(batch)), BATCH_SCHEMA,
                                "labels", lambda t, i=ids: _parse(t, i))
            except AiUnavailable as e:
                print(f"{name}: a batch failed: {e}")
                continue
            for short, lab in got.items():
                labels[name][batch[int(short) - 1].id] = lab.model_dump()
            print(f"{name}: {len(got)} of {len(batch)} labelled", flush=True)

    both = [a for a in articles if a.id in labels["haiku_55"] and a.id in labels["opus_55"]]
    print(f"\nRESULT: both labelled {len(both)} of {len(articles)} articles")
    for f in FIELDS:
        same = sum(labels["haiku_55"][a.id][f] == labels["opus_55"][a.id][f] for a in both)
        print(f"  agree on {f:17} {same} of {len(both)}")
    for name, m in ai.models.items():
        if m.calls:
            print(f"  {name}: {m.calls} calls, {m.tokens_in} tokens in, {m.tokens_out} out, "
                  f"about ${m.cost_usd:.3f}")
    print("\nWhere Haiku and Opus differ on the kind or the incident facts (earlier label in []):")
    for a in both:
        h, o = labels["haiku_55"][a.id], labels["opus_55"][a.id]
        if any(h[f] != o[f] for f in FIELDS[:6]):
            print(f"  [{a.lang}] {a.title[:90]}\n      haiku: {short(h)}\n      opus:  {short(o)}"
                  f"\n      [{a.labelled_by}: {short(a.label.model_dump())}]")
    print("\nJSON", json.dumps({"labels": labels}, ensure_ascii=False)[:200], "...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
