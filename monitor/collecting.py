"""Stage 0, collection: fetch the news and the official readings this pipeline works from.

Until 2026-11-21 the old pipeline did this (its hourly collector, and its twice-daily run for
the rest) and this pipeline read its files. Now this pipeline does it, with the same adapters:

- every hour: the RSS feeds and the GDELT DOC queries, into the 48-hour news buffer
  (rss_buffer.json), which ingest reads;
- in a scoring hour, as the old twice-daily run did: the sources that are not fetched hourly
  (pages scraped from HTML, JSON lists, ReliefWeb, feeds marked hourly: false), the official
  threat levels and travel advice, and the GDELT GKG media counts (baselines.json).

A failed source never stops the run: its health record says what went wrong.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from pipeline import anchors as anchor_reader
from pipeline import collect as old_collect
from pipeline import main as old_main
from pipeline.adapters.base import FetchResult
from pipeline.health import source_health
from pipeline.models import AnchorReading, RssBuffer, SourceHealth
from pipeline.process.dedupe import dedupe
from pipeline.store import state as buffer_store

from . import store

log = logging.getLogger("monitor.collect")

HOURLY_ADAPTERS = ("rss", "gdelt_doc")
SEEN_DAYS = 30
# A source fetched hourly counts the items it delivered in this long: an hour holds too few
# for a quiet feed, and six empty runs in a row mark a source stale (pipeline.health).
COUNT_WINDOW = timedelta(hours=24)


def hourly(source: dict) -> bool:
    return source["adapter"] in HOURLY_ADAPTERS and source.get("hourly", True)


def load_seen(state_dir: Path) -> dict[str, str]:
    """When undated items were first seen, so they keep the same date (normalize)."""
    seen = store.load_json(state_dir, "seen.json", None)
    return seen if seen is not None else (store.read(state_dir / "seen.json") or {})


def load_health(state_dir: Path) -> dict[str, dict]:
    data = store.load_json(state_dir, "source_health.json", None) or \
        store.read(state_dir / "source_health.json") or {"sources": []}
    return {s["id"]: s for s in data["sources"]}


def load_anchors(state_dir: Path) -> list[AnchorReading]:
    """The official readings last published (summary.json), or the old pipeline's at the
    first run."""
    summary = store.load_public(state_dir, "summary.json") or \
        store.read(state_dir / "latest.json") or {}
    return [AnchorReading.model_validate(a) for a in summary.get("anchors", [])]


def collect(state_dir: Path, sources: list[dict], queries: list[dict], now: datetime,
            slot: bool) -> tuple[list[SourceHealth], list[AnchorReading], dict]:
    """Fetch, write the buffer, media counts and seen dates. Returns (health of every source,
    official readings, stats)."""
    enabled = [s for s in sources if s["enabled"]]
    every_hour = [s for s in enabled if hourly(s)]
    twice_daily = [s for s in enabled if not hourly(s) and s["adapter"] != "gdelt_gkg"]
    gkg = next((s for s in enabled if s["adapter"] == "gdelt_gkg"), None)

    try:
        buf, reset = buffer_store.load_buffer_full(state_dir), False
    except ValidationError:
        # A broken buffer costs the items it held, not the run (as the old collector did).
        log.exception("rss_buffer.json is invalid; starting a new buffer")
        buf, reset = RssBuffer(schema_version=1, updated_at=now, items=[]), True
    seen = load_seen(state_dir)
    since = old_collect.gdelt_since(buf.health, now)
    results = old_main.fetch_all(every_hour, queries, since, now, False)
    fresh = old_main.normalize_all(every_hour, results, now, seen)
    buffer_health = old_collect.update_health(buf.health, results, now)
    slot_results: dict[str, FetchResult] = {}
    if slot:
        slot_results = old_main.fetch_all(twice_daily, queries, since, now, False)
        fresh += old_main.normalize_all(twice_daily, slot_results, now, seen)
    old_ids = {i.id for i in buf.items}
    kept = [i for i in dedupe(buf.items + fresh) if now - i.fetched_at <= old_collect.KEEP]
    buffer_store.write_buffer(state_dir, kept, now, buffer_health)
    for i in kept:
        if i.published_estimated:
            seen.setdefault(i.id, i.published_at.isoformat())
    oldest = (now - timedelta(days=SEEN_DAYS)).isoformat()
    store.save_json(state_dir, "seen.json", {k: v for k, v in seen.items() if v >= oldest})

    anchors = load_anchors(state_dir)
    if slot:
        anchors = anchor_reader.read_all([a.model_dump(mode="json") for a in anchors], now)
        if gkg:
            baselines = buffer_store.load_baselines(state_dir)
            slot_results[gkg["id"]] = old_main.run_gkg(gkg, baselines, now)
            buffer_store.write_baselines(state_dir, baselines)

    # Health, as the old pipeline recorded it: a source fetched hourly is ok while it has
    # succeeded in the last 6 hours (GDELT: 24), so one failed hour is not an alarm; the others
    # by this run's fetch, and between scoring hours they keep their last record.
    previous = load_health(state_dir)
    results_now = old_main.collected_health(every_hour, kept, buffer_health,
                                            now - COUNT_WINDOW, now) | slot_results
    health = []
    for s in sources:
        if not s["enabled"]:
            health.append(source_health(s, None, previous.get(s["id"]), now))
        elif s["id"] in results_now:
            health.append(source_health(s, results_now[s["id"]], previous.get(s["id"]), now))
        elif s["id"] in previous:
            health.append(SourceHealth.model_validate(previous[s["id"]]))
    store.save_json(state_dir, "source_health.json", {
        "schema_version": 2, "sources": [h.model_dump(mode="json") for h in health]})
    failed = [r.source_id for r in (results | slot_results).values() if not r.ok]
    stats = {"new": sum(1 for i in kept if i.id not in old_ids), "buffered": len(kept),
             "failed": failed, "buffer_reset": reset}
    log.info("collected: %s", stats)
    return health, anchors, stats
