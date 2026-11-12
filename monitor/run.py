"""One hourly run: python -m monitor --state-dir state [--no-ai] [--force] [--force-score]

Every hour: ingest, label, match, publish. From a scoring slot's hour on, once per slot: score
and write the brief as well. The workflow commits the state directory to the data branch.

While the old pipeline runs beside this one (design section 12, step 8), this run only reads
what the old one collects: the hourly buffer, the official levels it read, its media counts
and its source health. It writes under v2/ only.

A stage that crashes is recorded as failed with its error, the stages that do not depend on
it still run, everything is written, and the run exits 1.
"""

import argparse
import json
import logging
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from pipeline import main as old_main
from pipeline.models import AnchorReading, SourceHealth
from pipeline.process.normalize import item_id
from pipeline.store import state as old_state

from . import incidents as inc
from . import publish, settings, status, store
from .ai.client import Ai
from .briefing import brief
from .ingest import ingest, prune
from .labelling import label
from .models import GeopoliticsFile, Stage
from .scoring import due_slot, score

log = logging.getLogger("monitor")
MIN_GAP = timedelta(minutes=40)
FIRST_RUN_HOURS = 6     # the first run takes only the newest articles, not two days of them
LOG_DAYS = 7


def _stage(stages: dict[str, Stage], name: str, fn):
    """Run a stage; a crash is recorded with its error instead of ending the run."""
    try:
        return fn()
    except Exception as e:  # recorded in status.json and the exit code, never hidden
        log.error("%s crashed:\n%s", name, traceback.format_exc())
        stages[name] = Stage(status="failed", detail=f"{type(e).__name__}: {e}"[:300])
        return None


def latest_slot(now: datetime, slots: dict[str, int]) -> str:
    """The id of the newest scoring slot whose hour has come: today's, or yesterday's last."""
    for name in sorted(slots, reverse=True):
        if now.hour >= slots[name]:
            return now.strftime("%Y-%m-%dT") + name
    return (now - timedelta(days=1)).strftime("%Y-%m-%dT") + max(slots)


def _queue_stage(stats: dict, done: str) -> Stage:
    detail = done + (f"; stopped early: {stats['stopped']}" if stats["stopped"] else "")
    return Stage(status="degraded" if stats["stopped"] and stats["waiting"] else "ok",
                 detail=detail)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m monitor")
    p.add_argument("--state-dir", type=Path, default=Path("state"))
    p.add_argument("--git-sha")
    p.add_argument("--commit-msg-file", type=Path)
    p.add_argument("--no-ai", action="store_true", help="ask no model: articles only wait")
    p.add_argument("--force", action="store_true", help="run even if the last run was recent")
    p.add_argument("--force-score", action="store_true", help="score now, whatever the hour")
    p.add_argument("--now", help="pretend it is this moment (ISO, for tests)")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    d = args.state_dir
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(UTC).replace(
        microsecond=0)
    before = store.load_public(d, "status.json")
    if before and not args.force and now - datetime.fromisoformat(before["updated_at"]) < MIN_GAP:
        log.info("the last run was at %s; nothing to do", before["updated_at"])
        return 0

    cfg = settings.load()
    cfg_score = yaml.safe_load((old_main.CONFIG / "scoring.yaml").read_text())
    sources, _ = old_main.load_config()
    groups = {s["id"]: s["group"] for s in sources}
    prefilter_cfg = yaml.safe_load((old_main.CONFIG / "keywords.yaml").read_text())["prefilter"]
    stages: dict[str, Stage] = {}

    # What the old pipeline collected.
    old_latest = old_state.load(d)["latest"] or {}
    anchors = [AnchorReading.model_validate(a) for a in old_latest.get("anchors", [])]
    health = [SourceHealth.model_validate(s) for s in
              (store.read(d / "source_health.json") or {"sources": []})["sources"]]
    baselines = old_state.load_baselines(d)

    articles = store.load_articles(d)
    incidents = store.load_incidents(d)
    removed = store.load_removed(d)
    first_run = incidents is None
    if first_run:
        incidents = inc.seed(old_state.load_events(d), removed, now,
                             cfg["incidents"]["keep_days"], item_id)
        log.info("first run: %d incidents carried over from the old pipeline", len(incidents))
    history = store.load_public(d, "history.json")
    scoring = store.load_json(d, "scoring.json", None)
    if history is None or scoring is None:
        # The index continues from the old pipeline's history instead of starting again.
        rows, scoring = old_state.load_timeseries(d), old_state.load_scoring_state(d)
    else:
        rows = history["rows"]
    ai = None if args.no_ai else Ai.from_env(cfg["ai"])
    if ai is not None and not ai.keys:
        ai = None

    def do_ingest():
        hours = FIRST_RUN_HOURS if first_run and not articles else cfg["label"]["max_age_hours"]
        new = ingest(articles, old_state.load_buffer(d), groups, prefilter_cfg, now, hours)
        prune(articles, now)
        stages["ingest"] = Stage(status="ok", detail=f"{new} new articles, {len(articles)} kept")
        return new
    new_articles = _stage(stages, "ingest", do_ingest) or 0

    quiet = now.hour in cfg["quiet_hours"]
    resting = "left for the next hour: the old pipeline is using the AI allowance now"

    def do_label():
        if ai is None or quiet:
            stages["label"] = Stage(status="skipped", detail=resting if quiet else "no AI")
            return {}
        stats = label(articles, ai, cfg["label"], now)
        stages["label"] = _queue_stage(stats, f"{stats['labelled']} labelled, "
                                       f"{stats['waiting']} waiting, {stats['given_up']} given up")
        return stats
    lstats = _stage(stages, "label", do_label) or {}

    def do_match():
        if ai is None or quiet:
            stages["match"] = Stage(status="skipped", detail=resting if quiet else "no AI")
            return {}
        stats = inc.match(articles, incidents, ai, cfg["match"], now)
        stages["match"] = _queue_stage(stats, f"{stats['new']} new incidents, "
                                       f"{stats['attached']} reports added, "
                                       f"{stats['waiting']} waiting")
        return stats
    mstats = _stage(stages, "match", do_match) or {}
    corrections = inc.apply_overrides(incidents, articles, settings.overrides(), removed, now)
    incidents = inc.prune(incidents, now, cfg["incidents"]["keep_days"])

    slot = due_slot(now, cfg["score"]["slots"], rows)
    if args.force_score and slot is None:
        # Score the latest slot again: its rows are replaced, so the history keeps one value
        # per slot.
        slot = latest_slot(now, cfg["score"]["slots"])
        rows[:] = [r for r in rows if r["run_id"] != slot]

    def do_score():
        if slot is None:
            stages["score"] = Stage(status="skipped", detail="not a scoring hour")
            return None
        t = score(slot, incidents, anchors, baselines, rows, scoring, ai, now, cfg_score,
                  cfg["score"]["max_events"])
        levels = (f"SK {t.SK.level}/{t.SK.index}, EU {t.EU.level}/{t.EU.index}" if t
                  else "no level: no component has a value")
        stages["score"] = Stage(status="ok" if t else "degraded", detail=f"{slot}: {levels}")
        return (slot, t)
    scored = _stage(stages, "score", do_score)

    def do_brief():
        previous = store.load_public(d, "geopolitics.json")
        geo, stats = brief(articles, GeopoliticsFile.model_validate(previous) if previous
                           else None, baselines, ai, slot is not None, now, cfg["brief"],
                           cfg_score, old_main.CONFIG)
        if slot is None:
            stages["brief"] = Stage(status="skipped", detail="not a scoring hour")
        else:
            stages["brief"] = Stage(
                status="degraded" if stats["stale"] else "ok",
                detail=f"{len(stats['written'])} theatres written, {len(stats['carried'])} "
                       f"carried" + (f", failed: {stats['failed']}" if stats["failed"] else ""))
        store.write_public(d, "geopolitics.json", geo)
        return geo, stats
    geo_out = _stage(stages, "brief", do_brief)

    def do_publish():
        facts = {"tesat": old_main.load_tesat(), "sis_annual": old_main.load_sis_annual(),
                 "gtd": old_main.load_gtd()}
        summary = publish.summary_file(d, scored, anchors, health, incidents, facts, now)
        publish.incidents_files(d, incidents, corrections, now, cfg["incidents"]["current_days"])
        publish.reports_file(d, articles, now)
        stages["publish"] = Stage(status="ok", detail="files written")
        return summary
    summary = _stage(stages, "publish", do_publish)

    # Memory for the next run. Written even when a later stage crashed, so labels are kept.
    store.save_articles(d, articles, now)
    store.save_incidents(d, incidents, removed, now)
    store.save_json(d, "scoring.json", scoring)
    publish.history_file(d, rows)

    geo, bstats = geo_out if geo_out else (None, {"stale": []})
    written = [t.written_at for t in geo.theatres if t.written_at] if geo else []
    finished = now if args.now else datetime.now(UTC).replace(microsecond=0)
    st = status.build(
        finished, now, args.git_sha, stages, articles, health,
        summary.terrorism if summary else None, summary.scored_at if summary else None,
        summary.run_id if summary else None, bstats["stale"], min(written, default=None), ai, cfg)
    store.write_public(d, "status.json", st)
    runs = store.load_json(d, "log.json", [])
    runs.append({"at": finished.isoformat(), "overall": st.overall, "reasons": st.reasons,
                 "new": new_articles, "labelled": lstats.get("labelled", 0),
                 "waiting": st.queue.waiting_label, "scored": slot})
    oldest = (finished - timedelta(days=LOG_DAYS)).isoformat()
    store.save_json(d, "log.json", [r for r in runs if r["at"] >= oldest])

    msg = (f"monitor {now:%Y-%m-%dT%H:%M} {st.overall}: +{new_articles} articles, "
           f"{lstats.get('labelled', 0)} labelled, {st.queue.waiting_label} waiting, "
           f"{mstats.get('new', 0)} new incidents, {mstats.get('attached', 0)} reports added"
           + (f", scored {stages['score'].detail}" if slot else ""))
    log.info(msg)
    log.info("status: %s", json.dumps(st.reasons, ensure_ascii=False))
    if args.commit_msg_file:
        args.commit_msg_file.write_text(msg + "\n")
    return 1 if st.overall == "failed" else 0
