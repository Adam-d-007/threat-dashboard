"""Stage 4, publish: the small files the website reads (design section 9). Each page fetches
only what it shows, instead of one file with everything in it."""

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from pipeline.models import AnchorReading, Terrorism, Timeseries

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


def summary_file(state_dir: Path, scored: tuple[str, Terrorism | None] | None,
                 anchors: list[AnchorReading], facts: dict, now: datetime) -> Summary:
    """summary.json. scored is (run id, levels) when this run scored; otherwise the levels of
    the last scoring are kept and only the official readings are refreshed."""
    previous = store.load_public(state_dir, "summary.json")
    if scored:
        run_id, terrorism, scored_at = scored[0], scored[1], now
    elif previous:
        kept = Summary.model_validate(previous)
        run_id, terrorism, scored_at = kept.run_id, kept.terrorism, kept.scored_at
    else:
        run_id, terrorism, scored_at = None, None, None
    summary = Summary(schema_version=2, run_id=run_id, scored_at=scored_at, terrorism=terrorism,
                      anchors=anchors, **facts)
    store.write_public(state_dir, "summary.json", summary)
    return summary


def history_file(state_dir: Path, rows: list[dict]) -> None:
    store.write_public(state_dir, "history.json",
                       Timeseries(schema_version=1, rows=rows, sample=False))
