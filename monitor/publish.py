"""Stage 4, publish: the small files the website reads (design section 9). Each page fetches
only what it shows, instead of one file with everything in it."""

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from pipeline import main as old_main
from pipeline.models import (
    AnchorReading,
    Diff,
    LevelChange,
    SourceHealth,
    Terrorism,
    Timeseries,
)

from . import store
from .models import (
    Article,
    Correction,
    Incident,
    IncidentsFile,
    ReportsFile,
    Summary,
)

REPORT_HOURS = 48


def incidents_files(state_dir: Path, incidents: list[Incident], corrections: list[Correction],
                    now: datetime, current_days: int) -> None:
    """incidents/current.json (the last current_days, newest first) and one file per month of
    the incidents still in memory; older months keep the file last written for them."""
    def newest_first(rows: list[Incident]) -> list[Incident]:
        return sorted(rows, key=lambda i: (i.date, i.last_updated), reverse=True)

    since = (now - timedelta(days=current_days)).date()
    store.write_public(state_dir, "incidents/current.json", IncidentsFile(
        schema_version=2, updated_at=now, corrections=corrections,
        incidents=newest_first([i for i in incidents if i.date >= since])))
    months = defaultdict(list)
    for i in incidents:
        months[i.date.strftime("%Y-%m")].append(i)
    for month, rows in months.items():
        store.write_public(state_dir, f"incidents/{month}.json", IncidentsFile(
            schema_version=2, updated_at=now, incidents=newest_first(rows)))


def reports_file(state_dir: Path, articles: dict[str, Article], now: datetime) -> None:
    since = now - timedelta(hours=REPORT_HOURS)
    rows = [a for a in articles.values()
            if a.label and a.label.kind != "none" and a.published_at >= since]
    store.write_public(state_dir, "reports.json", ReportsFile(
        schema_version=2, updated_at=now,
        reports=sorted(rows, key=lambda a: a.published_at, reverse=True)))


def changes(before: dict | None, terrorism: Terrorism | None, anchors: list[AnchorReading],
            health: list[SourceHealth], incidents: list[Incident]) -> Diff:
    """What changed since the previous scoring run: official readings and source states (the
    old pipeline's comparison), incidents first seen since, and levels. before is the snapshot
    kept at that scoring; None at the first one."""
    if before is None:
        return Diff()
    out = old_main.diff({"anchors": before["anchors"], "sources": before["sources"]}, anchors,
                        health)
    since = datetime.fromisoformat(before["at"])
    out.new_event_ids = [i.id for i in incidents if i.first_seen > since]
    if terrorism:
        out.level_changes = [
            LevelChange(region=r, level_from=before["levels"].get(r),
                        level_to=getattr(terrorism, r).level)
            for r in ("SK", "EU") if before["levels"].get(r) != getattr(terrorism, r).level]
    return out


def snapshot(terrorism: Terrorism | None, anchors: list[AnchorReading],
             health: list[SourceHealth], now: datetime) -> dict:
    """What the next scoring run compares itself with."""
    return {"at": now.isoformat(),
            "anchors": [a.model_dump(mode="json") for a in anchors],
            "sources": [{"id": h.id, "status": h.status} for h in health],
            "levels": {r: getattr(terrorism, r).level for r in ("SK", "EU")} if terrorism else {}}


def summary_file(state_dir: Path, scored: tuple[str, Terrorism | None] | None,
                 anchors: list[AnchorReading], health: list[SourceHealth],
                 incidents: list[Incident], facts: dict, now: datetime) -> Summary:
    """summary.json. scored is (run id, levels) when this run scored; otherwise the levels and
    the changes of the last scoring are kept and only the official readings are refreshed."""
    previous = store.load_public(state_dir, "summary.json")
    kept = Summary.model_validate(previous) if previous else None
    if scored:
        run_id, terrorism, scored_at = scored[0], scored[1], now
        diff = changes(store.load_json(state_dir, "scored.json", None), terrorism, anchors,
                       health, incidents)
        store.save_json(state_dir, "scored.json", snapshot(terrorism, anchors, health, now))
    elif kept:
        run_id, terrorism, scored_at, diff = kept.run_id, kept.terrorism, kept.scored_at, kept.diff
    else:
        run_id, terrorism, scored_at, diff = None, None, None, None
    summary = Summary(schema_version=2, run_id=run_id, scored_at=scored_at, terrorism=terrorism,
                      diff=diff, anchors=anchors, **facts)
    store.write_public(state_dir, "summary.json", summary)
    return summary


def history_file(state_dir: Path, rows: list[dict]) -> None:
    store.write_public(state_dir, "history.json",
                       Timeseries(schema_version=1, rows=rows, sample=False))
