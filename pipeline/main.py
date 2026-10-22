"""One pipeline run: python -m pipeline.main [--no-llm] [--fixtures] [--slot 04|13]

Stages so far: load state, fetch, read official levels (anchors), normalize, merge the
hourly RSS buffer, dedupe, window filter, diff, write. The workflow commits the state
directory to the data branch afterwards.
"""

import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from pydantic import ValidationError

from . import anchors as anchor_reader
from .adapters import acled, gdelt_doc, gdelt_gkg, html_scrape, json_api, reliefweb, rss
from .adapters.base import FetchError, FetchResult
from .health import run_status, source_health
from .models import (
    SCHEMA_VERSION,
    AnchorReading,
    Diff,
    Item,
    Run,
    RunCounts,
    RunInfo,
    SourceHealth,
    Tesat,
    TesatYear,
    ValueChange,
)
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
            # A source may carry its own queries (e.g. outlets only reachable through GDELT).
            return gdelt_doc.fetch(src, src.get("queries") or queries, since, now)
        if src["adapter"] == "rss":
            return rss.fetch(src)
        if src["adapter"] == "html_scrape":
            return html_scrape.fetch(src)
        if src["adapter"] == "json_api":
            return json_api.fetch(src)
        if src["adapter"] == "acled":
            return acled.fetch(src, now)
        if src["adapter"] == "reliefweb":
            return reliefweb.fetch(src, since)
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


def load_config() -> tuple[list[dict], list[dict]]:
    """All sources from sources.yaml and the GDELT DOC queries from keywords.yaml."""
    sources = yaml.safe_load((CONFIG / "sources.yaml").read_text())["sources"]
    queries = yaml.safe_load((CONFIG / "keywords.yaml").read_text())["gdelt_doc"]["queries"]
    return sources, queries


def normalize_all(sources: list[dict], results: dict[str, FetchResult], now: datetime,
                  seen: dict[str, str]) -> list[Item]:
    """Normalize every fetched item. An item that fails validation is dropped and noted in
    its source's error text, so it shows on the sources page."""
    items: list[Item] = []
    for src in sources:
        res = results[src["id"]]
        bad = []
        for raw in res.items:
            try:
                items.append(normalize(raw, src, now, seen))
            except ValidationError as e:
                bad.append(f"{raw.url}: {e.errors()[0]['msg']}")
        if bad:
            log.warning("%s: %d items failed to normalize, first: %s", src["id"], len(bad), bad[0])
            res.error = "; ".join(filter(None, [res.error,
                                                f"{len(bad)} items failed to normalize: {bad[0]}"]))
        log.info("%-10s ok=%s items=%d %s", src["id"], res.ok, len(res.items), res.error or "")
    return items


def fixture_fetch(src: dict) -> FetchResult:
    """Sources without a fixture file return an empty, successful result."""
    if src["adapter"] == "gdelt_doc" and (FIXTURES / f"{src['id']}.json").exists():
        items = gdelt_doc.parse(json.loads((FIXTURES / f"{src['id']}.json").read_text()))
    elif (FIXTURES / f"{src['id']}.xml").exists():
        items = rss.parse((FIXTURES / f"{src['id']}.xml").read_bytes())
    else:
        items = []
    return FetchResult(source_id=src["id"], ok=True, items=items, http_status=200)


def diff(prev_run: dict | None, anchors: list[AnchorReading],
         health: list[SourceHealth]) -> Diff:
    """Official level and source status changes since the previous run."""
    if not prev_run:
        return Diff()
    prev_anchors = {a["id"]: a for a in prev_run.get("anchors", [])}
    prev_sources = {s["id"]: s["status"] for s in prev_run.get("sources", [])}
    anchor_changes = []
    for a in anchors:
        old = prev_anchors.get(a.id)
        if old is None or a.raw is None:
            continue
        if old.get("raw") != a.raw:
            anchor_changes.append(ValueChange(id=a.id, value_from=old.get("raw"), value_to=a.raw))
        elif old.get("text_hash") and a.text_hash and old["text_hash"] != a.text_hash:
            # Same level, different wording: worth a look (the SIS paragraph especially).
            anchor_changes.append(ValueChange(id=a.id, value_from="text", value_to="text changed"))
    source_changes = [ValueChange(id=h.id, value_from=prev_sources[h.id], value_to=h.status)
                      for h in health if h.id in prev_sources and prev_sources[h.id] != h.status]
    return Diff(anchor_changes=anchor_changes, source_changes=source_changes)


def load_tesat() -> Tesat | None:
    """TE-SAT figures from manual_anchors.yaml, or None while they are not filled in."""
    t = yaml.safe_load((CONFIG / "manual_anchors.yaml").read_text()).get("tesat") or {}
    if t.get("attacks_total") is None:
        return None
    year = {k: t.get(k) for k in ("data_year", "attacks_total", "attacks_completed",
                                  "member_states_with_attacks", "fatalities", "arrests_total")}
    prev = t.get("previous_year")
    return Tesat(report_year=t["report_year"], url=t["url"], current=TesatYear(**year),
                 attacks_failed=t["attacks_failed"], attacks_foiled=t["attacks_foiled"],
                 attacks_by_ideology=t["attacks_by_ideology"],
                 arrests_by_ideology=t["arrests_by_ideology"],
                 slovakia_attacks=t["slovakia"]["attacks"],
                 slovakia_arrests=t["slovakia"]["arrests"],
                 previous=TesatYear(**prev) if prev else None)


def run_gkg(src: dict, baselines: dict, now: datetime) -> FetchResult:
    """Read new GKG files into baselines (in place). Missing files make the source failed only
    when nothing could be read at all."""
    try:
        records, missing, error = gdelt_gkg.fetch(src, set(baselines["gkg"]["processed"]))
    except FetchError as e:
        return FetchResult(source_id=src["id"], ok=False, error=str(e))
    state.merge_gkg(baselines, records, now)
    log.info("gdelt_gkg  files=%d missing=%d", len(records), len(missing))
    return FetchResult(source_id=src["id"], ok=bool(records) or not missing,
                       error=error, http_status=200)


def prev_anchors_as_models(previous: list[dict]) -> list[AnchorReading]:
    """Fixture runs make no network calls, so they carry the previous anchors forward."""
    return [AnchorReading.model_validate(a) for a in previous]


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
    p.add_argument("--skip-if-slot-done", action="store_true",
                   help="exit without writing when this slot already has a successful run "
                        "(backup cron entries use this, because GitHub can drop scheduled runs)")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    started = FIXTURE_NOW if args.fixtures else datetime.now(UTC).replace(microsecond=0)
    prev = state.load(args.state_dir)
    this_run = run_id(started, args.slot)
    if args.skip_if_slot_done and prev["latest"] and prev["latest"]["run"]["id"] == this_run:
        log.info("slot %s already has a %s run; nothing to do", this_run,
                 prev["latest"]["run"]["status"])
        return 0
    since = window_start(prev["latest"], started)
    sources, queries = load_config()
    enabled = [s for s in sources if s["enabled"] and s["adapter"] != "gdelt_gkg"]
    gkg_src = next((s for s in sources if s["enabled"] and s["adapter"] == "gdelt_gkg"), None)
    log.info("run %s window from %s, %d sources enabled",
             run_id(started, args.slot), since.isoformat(), len(enabled))

    results = fetch_all(enabled, queries, since, started, args.fixtures)
    baselines = state.load_baselines(args.state_dir)
    if gkg_src and not args.fixtures:
        results[gkg_src["id"]] = run_gkg(gkg_src, baselines, started)
    prev_anchors = (prev["latest"] or {}).get("anchors", [])
    anchors = prev_anchors_as_models(prev_anchors) if args.fixtures else \
        anchor_reader.read_all(prev_anchors, started)

    seen: dict[str, str] = dict(prev["seen"])
    items = normalize_all(enabled, results, started, seen)

    enabled_ids = {s["id"] for s in enabled}
    try:
        buffered = [i for i in state.load_buffer(args.state_dir) if i.source_id in enabled_ids]
        buffer_ok = True
    except ValidationError:
        # A broken buffer costs the items it holds, not the run; the run shows as partial.
        log.exception("rss_buffer.json is invalid; continuing with this run's own fetch only")
        buffered, buffer_ok = [], False
    log.info("buffer     items=%d", len(buffered))

    unique = dedupe(items + buffered)
    # Remember when undated items were first seen, so later runs keep the same date.
    for i in unique:
        if i.published_estimated:
            seen.setdefault(i.id, i.published_at.isoformat())
    in_window = sorted((i for i in unique if i.published_at >= since),
                       key=lambda i: i.published_at, reverse=True)

    health = [source_health(s, results.get(s["id"]) if s["enabled"] else None,
                            prev["health"].get(s["id"]), started) for s in sources]
    finished = started if args.fixtures else datetime.now(UTC).replace(microsecond=0)
    status = run_status(health) if buffer_ok else "partial"
    info = RunInfo(id=run_id(started, args.slot), status=status, started_at=started,
                   finished_at=finished, window_start=since, git_sha=args.git_sha,
                   counts=RunCounts(fetched=len(items), from_buffer=len(buffered),
                                    after_dedupe=len(unique), in_window=len(in_window)))
    run = Run(schema_version=SCHEMA_VERSION, run=info, sources=health, items=in_window,
              anchors=anchors, diff=diff(prev["latest"], anchors, health), tesat=load_tesat())

    try:
        state.write(args.state_dir, run, seen, finished)
        if gkg_src and not args.fixtures:
            state.write_baselines(args.state_dir, baselines)
        if (res := results.get("acled")) and res.ok:
            state.write_acled(args.state_dir, res.records, finished)
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
