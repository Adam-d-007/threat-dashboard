"""One pipeline run: python -m pipeline.main [--no-llm] [--fixtures] [--slot 04|13]

Phase 1 stages: load state, fetch, normalize, dedupe, window filter, write.
The workflow commits the state directory to the data branch afterwards.
"""

import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from pydantic import ValidationError

from .adapters import gdelt_doc, rss
from .adapters.base import FetchResult
from .health import run_status, source_health
from .models import SCHEMA_VERSION, Item, Run, RunCounts, RunInfo
from .process.dedupe import dedupe
from .process.normalize import normalize
from .store import state

CONFIG = Path(__file__).parent / "config"
FIXTURES = Path(__file__).parent / "fixtures"
OVERLAP = timedelta(hours=2)
MAX_WINDOW = timedelta(hours=36)
# --fixtures runs pretend it is this moment, so their output never depends on the date.
FIXTURE_NOW = datetime(2026, 10, 22, 11, 0, tzinfo=UTC)

log = logging.getLogger("pipeline")


def window_start(previous: dict | None, now: datetime) -> datetime:
    """From the last successful run's start minus 2 h of overlap, at most 36 h back."""
    earliest = now - MAX_WINDOW
    if not previous or previous["run"]["status"] == "failed":
        return earliest
    return max(datetime.fromisoformat(previous["run"]["started_at"]) - OVERLAP, earliest)


def fetch_all(sources: list[dict], queries: list[dict], since: datetime, now: datetime,
              use_fixtures: bool) -> dict[str, FetchResult]:
    """Non-GDELT adapters run in parallel; GDELT runs on its own thread, one call at a time."""
    def run_one(src: dict) -> FetchResult:
        if use_fixtures:
            return fixture_fetch(src)
        if src["adapter"] == "gdelt_doc":
            return gdelt_doc.fetch(src, queries, since, now)
        if src["adapter"] == "rss":
            return rss.fetch(src)
        raise ValueError(f"unknown adapter {src['adapter']!r} for {src['id']}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {s["id"]: pool.submit(run_one, s) for s in sources}
        results = {}
        for sid, fut in futures.items():
            try:
                results[sid] = fut.result()
            except Exception as e:  # an adapter bug fails its source, never the run
                log.exception("adapter crashed for %s", sid)
                results[sid] = FetchResult(source_id=sid, ok=False,
                                           error=f"adapter crashed: {type(e).__name__}: {e}")
    return results


def fixture_fetch(src: dict) -> FetchResult:
    if src["adapter"] == "gdelt_doc":
        items = gdelt_doc.parse(json.loads((FIXTURES / f"{src['id']}.json").read_text()))
    else:
        items = rss.parse((FIXTURES / f"{src['id']}.xml").read_bytes())
    return FetchResult(source_id=src["id"], ok=True, items=items, http_status=200)


def run_id(now: datetime, slot: str | None) -> str:
    return now.strftime("%Y-%m-%dT") + (slot or now.strftime("%H"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m pipeline.main")
    p.add_argument("--no-llm", action="store_true", help="skip LLM stages (no LLM yet in Phase 1)")
    p.add_argument("--fixtures", action="store_true", help="read pipeline/fixtures, no network")
    p.add_argument("--slot", choices=["04", "13"], help="override the hour in the run id")
    p.add_argument("--state-dir", type=Path, default=Path("state"))
    p.add_argument("--git-sha")
    p.add_argument("--commit-msg-file", type=Path)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    started = FIXTURE_NOW if args.fixtures else datetime.now(UTC).replace(microsecond=0)
    prev = state.load(args.state_dir)
    since = window_start(prev["latest"], started)
    sources = yaml.safe_load((CONFIG / "sources.yaml").read_text())["sources"]
    queries = yaml.safe_load((CONFIG / "keywords.yaml").read_text())["gdelt_doc"]["queries"]
    enabled = [s for s in sources if s["enabled"]]
    log.info("run %s window from %s, %d sources enabled",
             run_id(started, args.slot), since.isoformat(), len(enabled))

    results = fetch_all(enabled, queries, since, started, args.fixtures)

    seen: dict[str, str] = dict(prev["seen"])
    items: list[Item] = []
    for src in enabled:
        res = results[src["id"]]
        bad = []
        for raw in res.items:
            try:
                item = normalize(raw, src, started, seen)
            except ValidationError as e:
                bad.append(f"{raw.url}: {e.errors()[0]['msg']}")
                continue
            seen.setdefault(item.id, started.isoformat())
            items.append(item)
        if bad:
            log.warning("%s: %d items failed to normalize, first: %s", src["id"], len(bad), bad[0])
            res.error = "; ".join(filter(None, [res.error,
                                                f"{len(bad)} items failed to normalize: {bad[0]}"]))
        log.info("%-10s ok=%s items=%d %s", src["id"], res.ok, len(res.items), res.error or "")

    unique = dedupe(items)
    in_window = sorted((i for i in unique if i.published_at >= since),
                       key=lambda i: i.published_at, reverse=True)

    health = [source_health(s, results.get(s["id"]) if s["enabled"] else None,
                            prev["health"].get(s["id"]), started) for s in sources]
    finished = started if args.fixtures else datetime.now(UTC).replace(microsecond=0)
    info = RunInfo(id=run_id(started, args.slot), status=run_status(health), started_at=started,
                   finished_at=finished, window_start=since, git_sha=args.git_sha,
                   counts=RunCounts(fetched=len(items), after_dedupe=len(unique),
                                    in_window=len(in_window)))
    run = Run(schema_version=SCHEMA_VERSION, run=info, sources=health, items=in_window)

    try:
        state.write(args.state_dir, run, seen, finished)
    except ValidationError:
        log.exception("run failed validation; latest.json left unchanged")
        run.run.status = "failed"
        state.write_failed(args.state_dir, run, seen, finished)

    msg = f"run {run.run.id} {run.run.status} items {len(run.items)}"
    log.info(msg)
    if args.commit_msg_file:
        args.commit_msg_file.write_text(msg + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
