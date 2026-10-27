"""One pipeline run: python -m pipeline.main [--no-llm] [--fixtures] [--slot 04|13]

Stages: load state, fetch, read official levels (anchors), normalize, merge the hourly RSS
buffer, dedupe (exact and near), window filter, prefilter, classify (LLM, rules fallback),
geocode, cluster into events, score both regions, diff, write. The workflow commits the
state directory to the data branch afterwards.
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
from .adapters import gdelt_doc, gdelt_gkg, html_scrape, json_api, reliefweb, rss
from .adapters.base import FetchError, FetchResult
from .health import run_status, source_health
from .llm.client import LlmClient
from .models import (
    SCHEMA_VERSION,
    AnchorReading,
    Brief,
    Diff,
    Gtd,
    Item,
    LevelChange,
    LlmUsage,
    Run,
    RunCounts,
    RunInfo,
    SisAnnual,
    SourceHealth,
    Terrorism,
    Tesat,
    TesatYear,
    ValueChange,
)
from .process.classify import classify
from .process.cluster import cluster
from .process.dedupe import dedupe
from .process.geocode import geocode
from .process.normalize import normalize
from .process.prefilter import prefilter
from .score import geopolitics
from .score.terrorism import score_region, update_anchor_history
from .store import state

CONFIG = Path(__file__).parent / "config"
FIXTURES = Path(__file__).parent / "fixtures"
GTD = Path(__file__).parents[1] / "static" / "gtd_aggregates.json"
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


def understand(items: list[Item], groups: dict[str, str], client: LlmClient | None,
               cache: dict, events: list, now: datetime) -> tuple[list[Item], list, list, dict]:
    """Prefilter, classify, geocode and cluster. Returns (prefiltered items, events, new event
    ids, classification stats)."""
    cfg_pre = yaml.safe_load((CONFIG / "keywords.yaml").read_text())["prefilter"]
    cfg_llm = yaml.safe_load((CONFIG / "scoring.yaml").read_text())["llm"]
    kept = prefilter(items, groups, cfg_pre)
    refs, stats = classify(kept, client, cfg_llm, cache)
    for item in kept:
        if item.classification and refs.get(item.id):
            item.classification.places = geocode(refs[item.id])
    events, new_ids = cluster(kept, events, now)
    return kept, events, new_ids, stats


def llm_usage(client: LlmClient | None, stats: dict) -> LlmUsage:
    if client is None or not client.providers:
        return LlmUsage(status="disabled", items_rules=stats["rules"],
                        items_cached=stats["cached"])
    u = client.usage()
    fell_back = stats["rules"] > 0 or stats["batches_failed"] > 0
    return LlmUsage(status="fallback" if fell_back else "ok", provider=u["provider"],
                    model=u["model"], calls=u["calls"], fallback_used=u["fallback_used"],
                    items_llm=stats["llm"], items_rules=stats["rules"],
                    items_cached=stats["cached"])


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


def load_sis_annual() -> SisAnnual | None:
    """The SIS annual report summary from manual_anchors.yaml, or None while it is empty."""
    s = yaml.safe_load((CONFIG / "manual_anchors.yaml").read_text()).get("sis_annual") or {}
    if not s.get("report_year"):
        return None
    return SisAnnual(**s)


def load_gtd() -> Gtd | None:
    """GTD yearly counts from static/gtd_aggregates.json, or None until Adam has run
    pipeline.tools.gtd_aggregates on the GTD download."""
    return Gtd.model_validate_json(GTD.read_text()) if GTD.exists() else None


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


COLLECTED_FRESH = timedelta(hours=6)
# GDELT queries catch up from their own last success, up to 24 hours back (collect.py and
# topup_gdelt), so a query loses nothing until it has failed for a day: that is its limit.
GDELT_FRESH = timedelta(hours=24)


def collected_health(sources: list[dict], buffered: list[Item], health: dict[str, dict],
                     since: datetime, now: datetime) -> dict[str, FetchResult]:
    """Health for sources fetched by the hourly collector: ok when a run succeeded within
    6 hours (RSS) or, for GDELT queries, each query within 24 hours; the item count is the
    source's buffered items in this run's window."""
    out = {}
    for s in sources:
        h = health.get(s["id"], {})
        fresh = GDELT_FRESH if s.get("adapter") == "gdelt_doc" else COLLECTED_FRESH
        last = datetime.fromisoformat(h["last_success"]) if h.get("last_success") else None
        ok = last is not None and now - last <= fresh
        count = sum(1 for i in buffered if i.source_id == s["id"] and i.published_at >= since)
        out[s["id"]] = FetchResult(source_id=s["id"], ok=ok, item_count=count,
                                   error=None if ok else (h.get("error") or
                                   f"no successful run in {fresh.total_seconds() / 3600:.0f} h"))
    return out


def topup_gdelt(sources: list[dict], queries: list[dict], health: dict[str, dict],
                now: datetime) -> tuple[dict[str, FetchResult], dict[str, dict]]:
    """GitHub skips many hourly collector runs, so the pipeline itself runs any GDELT query
    with no success within COLLECTED_FRESH, from that query's last success (at most a day
    back). Returns (results, health with those successes merged). The merge is in memory
    only: rss_buffer.json stays the collector's file."""
    health = {k: dict(v) for k, v in health.items()}
    results = {}
    for src in sources:
        qs = src.get("queries") or queries
        h = health.setdefault(src["id"], {})
        parts = dict(h.get("parts") or {})
        stale = [q for q in qs if q["id"] not in parts
                 or now - datetime.fromisoformat(parts[q["id"]]) > COLLECTED_FRESH]
        if not stale:
            continue
        since = max(now - timedelta(hours=24),
                    min((datetime.fromisoformat(parts[q["id"]]) for q in stale
                         if q["id"] in parts), default=now - timedelta(hours=24)))
        log.info("%s: the pipeline runs %d stale GDELT queries itself", src["id"], len(stale))
        res = gdelt_doc.fetch(src, stale, since, now)
        parts |= dict.fromkeys(res.parts_ok, now.isoformat())
        h["parts"] = parts
        if all(q["id"] in parts for q in qs):
            h["last_success"] = min(parts[q["id"]] for q in qs)
        h["error"] = res.error
        results[src["id"]] = res
    return results, health


def carry_brief(prev_latest: dict) -> Brief | None:
    """When no model could write a brief, keep the last good one (it says when it was written)
    rather than show an empty box."""
    old = (prev_latest.get("geopolitics") or {}).get("brief") or {}
    if old.get("status") != "ok" or not old.get("lines"):
        return None
    brief = Brief.model_validate(old)
    url_of = {i["id"]: i["url"] for i in prev_latest.get("items", []) if i.get("url")}
    for line in brief.lines:
        if not line.urls:
            line.urls = [url_of[x] for x in line.item_ids if x in url_of]
    if brief.written_at is None:
        brief.written_at = datetime.fromisoformat(prev_latest["run"]["finished_at"])
    return brief


def prev_anchors_as_models(previous: list[dict]) -> list[AnchorReading]:
    """Fixture runs make no network calls, so they carry the previous anchors forward."""
    return [AnchorReading.model_validate(a) for a in previous]


def run_id(now: datetime, slot: str | None) -> str:
    return now.strftime("%Y-%m-%dT") + (slot or now.strftime("%H"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m pipeline.main")
    p.add_argument("--no-llm", action="store_true", help="label items with keyword rules only")
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
    # GDELT DOC is fetched by the hourly collector (see collect.py); its items arrive with the
    # buffer. Fixture runs read the GDELT fixture directly.
    fetched = enabled if args.fixtures else [s for s in enabled if s["adapter"] != "gdelt_doc"]
    gkg_src = next((s for s in sources if s["enabled"] and s["adapter"] == "gdelt_gkg"), None)
    log.info("run %s window from %s, %d sources enabled",
             run_id(started, args.slot), since.isoformat(), len(enabled))

    results = fetch_all(fetched, queries, since, started, args.fixtures)
    baselines = state.load_baselines(args.state_dir)
    if gkg_src and not args.fixtures:
        results[gkg_src["id"]] = run_gkg(gkg_src, baselines, started)
    prev_anchors = (prev["latest"] or {}).get("anchors", [])
    anchors = prev_anchors_as_models(prev_anchors) if args.fixtures else \
        anchor_reader.read_all(prev_anchors, started)

    seen: dict[str, str] = dict(prev["seen"])
    items = normalize_all(fetched, results, started, seen)

    enabled_ids = {s["id"] for s in enabled}
    try:
        buffered = [i for i in state.load_buffer(args.state_dir) if i.source_id in enabled_ids]
        buffer_ok = True
    except ValidationError:
        # A broken buffer costs the items it holds, not the run; the run shows as partial.
        log.exception("rss_buffer.json is invalid; continuing with this run's own fetch only")
        buffered, buffer_ok = [], False
    log.info("buffer     items=%d", len(buffered))
    if not args.fixtures:
        collected = [s for s in enabled if s not in fetched]
        health = state.load_buffer_full(args.state_dir).health if buffer_ok else {}
        topped, health = topup_gdelt([s for s in collected if s["adapter"] == "gdelt_doc"],
                                     queries, health, started)
        items += normalize_all([s for s in collected if s["id"] in topped], topped, started,
                               seen)
        results |= collected_health(collected, buffered + [i for i in items if i.source_id
                                                         in topped], health, since, started)

    unique = dedupe(items + buffered)
    # Remember when undated items were first seen, so later runs keep the same date.
    for i in unique:
        if i.published_estimated:
            seen.setdefault(i.id, i.published_at.isoformat())
    in_window = sorted((i for i in unique if i.published_at >= since),
                       key=lambda i: i.published_at, reverse=True)

    client = None if (args.no_llm or args.fixtures) else LlmClient.from_env(
        yaml.safe_load((CONFIG / "scoring.yaml").read_text())["llm"])
    cache = state.load_classified(args.state_dir)
    groups = {s["id"]: s["group"] for s in sources}
    kept, events, new_event_ids, cstats = understand(
        in_window, groups, client, cache, state.load_events(args.state_dir), started)
    relevant = [i for i in kept if i.classification and i.classification.relevant]
    # Events stored before they carried URLs get them from any report still at hand, including
    # the previous run's items (reports that have since left the buffer).
    url_of = {i["id"]: i["url"] for i in (prev["latest"] or {}).get("items", []) if i.get("url")}
    url_of |= {i.id: i.url for i in unique if i.url}
    missing = {i for e in events for i in e.item_ids if i not in url_of and not e.urls}
    if missing:
        url_of |= state.item_urls_from_runs(args.state_dir, missing)
    for e in events:
        e.urls.extend(u for u in (url_of.get(i) for i in e.item_ids) if u and u not in e.urls)
    recent = (started - timedelta(days=30)).date()

    cfg_score = yaml.safe_load((CONFIG / "scoring.yaml").read_text())
    scoring = state.load_scoring_state(args.state_dir)
    rows = state.load_timeseries(args.state_dir)
    update_anchor_history(scoring, anchors, started)
    call_limit = cfg_score["llm"]["budget"]["classify"] + cfg_score["llm"]["budget"]["assess"]
    regions = {}
    for region in ("SK", "EU"):
        regions[region], row = score_region(region, this_run, events, anchors, baselines, rows,
                                            scoring, client, started, cfg_score, call_limit)
        if row:
            rows.append(row)
    scored = all(regions.values())
    prev_latest = prev["latest"] or {}
    prev_brief = [line["text_en"] for line in
                  ((prev_latest.get("geopolitics") or {}).get("brief") or {}).get("lines", [])]
    geo = geopolitics.build(relevant, prev_latest.get("items", []), prev_brief, baselines, client,
                            started, cfg_score, CONFIG, call_limit)
    if geo.brief and geo.brief.status == "fallback":
        geo.brief = carry_brief(prev_latest) or geo.brief

    health = [source_health(s, results.get(s["id"]) if s["enabled"] else None,
                            prev["health"].get(s["id"]), started) for s in sources]
    finished = started if args.fixtures else datetime.now(UTC).replace(microsecond=0)
    usage = llm_usage(client, cstats)
    status = run_status(health, usage.status, started) if buffer_ok else "partial"
    info = RunInfo(id=run_id(started, args.slot), status=status, started_at=started,
                   finished_at=finished, window_start=since, git_sha=args.git_sha,
                   counts=RunCounts(fetched=len(items), from_buffer=len(buffered),
                                    after_dedupe=len(unique), in_window=len(in_window),
                                    after_prefilter=len(kept), relevant=len(relevant)),
                   llm=usage)
    run_diff = diff(prev["latest"], anchors, health)
    run_diff.new_event_ids = new_event_ids
    prev_terr = (prev["latest"] or {}).get("terrorism") or {}
    run_diff.level_changes = [
        LevelChange(region=r, level_from=(prev_terr.get(r) or {}).get("level"), level_to=a.level)
        for r, a in regions.items() if a and (prev_terr.get(r) or {}).get("level") != a.level]
    run = Run(schema_version=SCHEMA_VERSION, run=info, sources=health, items=relevant,
              anchors=anchors, diff=run_diff, tesat=load_tesat(),
              sis_annual=load_sis_annual(), gtd=load_gtd(),
              terrorism=Terrorism(SK=regions["SK"], EU=regions["EU"]) if scored else None,
              geopolitics=geo,
              events=sorted((e for e in events if e.date >= recent),
                            key=lambda e: e.date, reverse=True))

    try:
        state.write(args.state_dir, run, seen, finished)
        state.write_events(args.state_dir, events)
        state.write_classified(args.state_dir, cache, finished)
        state.write_timeseries(args.state_dir, rows)
        state.write_scoring_state(args.state_dir, scoring)
        if gkg_src and not args.fixtures:
            state.write_baselines(args.state_dir, baselines)
    except ValidationError:
        log.exception("run failed validation; latest.json left unchanged")
        run.run.status = "failed"
        state.write_failed(args.state_dir, run, seen, finished)

    levels = (f"SK {regions['SK'].level}/{regions['SK'].index} "
              f"EU {regions['EU'].level}/{regions['EU'].index}" if scored else "no score")
    msg = (f"run {run.run.id} {run.run.status} {levels} "
           f"items {len(run.items)} events {len(run.events)} "
           f"llm {run.run.llm.status} {run.run.llm.calls} calls")
    log.info(msg)
    if args.commit_msg_file:
        args.commit_msg_file.write_text(msg + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
