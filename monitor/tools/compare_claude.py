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


def facts(x: dict) -> str:
    return (f"{x['kind']} {x['domain']} {x['incident_type']} s{x['severity']} "
            f"{x['incident_date']} {x['incident_country']}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m monitor.tools.compare_claude")
    p.add_argument("--state-dir", type=Path, default=Path("state"))
    p.add_argument("--models", default="haiku_55",
                   help="comma-separated models to compare with opus_55, the reference")
    args = p.parse_args(argv)
    names = [*args.models.split(","), "opus_55"]

    cfg = settings.load()["ai"]
    ai = Ai.from_env(cfg)
    if "anthropic" not in ai.keys:
        print("ANTHROPIC_API_KEY is not set")
        return 1
    done = [a for a in store.load_articles(args.state_dir).values() if a.label]
    articles = sorted(done, key=lambda a: a.published_at, reverse=True)[:ARTICLES]
    size = settings.load()["label"]["batch_size"]
    batches = [articles[k:k + size] for k in range(0, len(articles), size)]
    labels: dict[str, dict[str, dict]] = {name: {} for name in names}
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
            for n, lab in got.items():
                labels[name][batch[int(n) - 1].id] = lab.model_dump()
            print(f"{name}: {len(got)} of {len(batch)} labelled", flush=True)

    ref = labels["opus_55"]
    print("\nRESULT")
    for name in names[:-1]:
        mine = labels[name]
        both = [a for a in articles if a.id in mine and a.id in ref]
        print(f"{name} against opus_55: both labelled {len(both)} of {len(articles)}")
        for f in FIELDS:
            same = sum(mine[a.id][f] == ref[a.id][f] for a in both)
            print(f"  agree on {f:17} {same} of {len(both)}")
    for name, m in ai.models.items():
        if m.calls:
            print(f"  {name}: {m.calls} calls, {m.tokens_in} tokens in, {m.tokens_out} out, "
                  f"about ${m.cost_usd:.3f}")
    print("\nWhere a model and Opus differ on a terrorism or hybrid report (the only ones that "
          "can make incidents):")
    for a in articles:
        o = ref.get(a.id)
        if not o:
            continue
        rows = [(n, labels[n][a.id]) for n in names[:-1] if a.id in labels[n]]
        counts = {"terrorism", "hybrid"} & {o["domain"], *(x["domain"] for _, x in rows)}
        if counts and any(any(x[f] != o[f] for f in FIELDS[:6]) for _, x in rows):
            print(f"  [{a.lang}] {a.title[:90]}")
            for n, x in rows:
                print(f"      {n:18} {facts(x)}")
            print(f"      {'opus_55':18} {facts(o)}")
    print("\nJSON", json.dumps({"labels": labels}, ensure_ascii=False)[:200], "...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
