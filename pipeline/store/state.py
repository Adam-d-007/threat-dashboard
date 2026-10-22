"""Read and write the files on the data branch (checked out at --state-dir)."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..models import Event, Item, RssBuffer, Run, SourceHealth

KEEP_RUNS = 28
SEEN_DAYS = 30
BUFFER_FILE = "rss_buffer.json"


def _read(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")


def load(state_dir: Path) -> dict:
    health = _read(state_dir / "source_health.json") or {"sources": []}
    return {
        "latest": _read(state_dir / "latest.json"),
        "health": {s["id"]: s for s in health["sources"]},
        "seen": _read(state_dir / "seen.json") or {},
    }


def write(state_dir: Path, run: Run, seen: dict[str, str], now: datetime) -> None:
    """Write a valid run as latest.json and runs/<id>.json, then the health and seen files."""
    data = Run.model_validate(run.model_dump()).model_dump(mode="json")
    _write(state_dir / "latest.json", data)
    _write(state_dir / "runs" / f"{run.run.id}.json", data)
    write_side_files(state_dir, run.sources, seen, now)


def write_failed(state_dir: Path, run: Run, seen: dict[str, str], now: datetime) -> None:
    """Record a failed run without touching latest.json."""
    data = run.model_copy(update={"items": []}).model_dump(mode="json")
    _write(state_dir / "runs" / f"{run.run.id}.json", data)
    write_side_files(state_dir, run.sources, seen, now)


def write_side_files(state_dir: Path, sources: list[SourceHealth], seen: dict[str, str],
                     now: datetime) -> None:
    _write(state_dir / "source_health.json",
           {"schema_version": 1, "sources": [s.model_dump(mode="json") for s in sources]})
    cutoff = now - timedelta(days=SEEN_DAYS)
    _write(state_dir / "seen.json",
           {k: v for k, v in seen.items() if datetime.fromisoformat(v) >= cutoff})
    runs = sorted(p for p in (state_dir / "runs").glob("*.json") if p.name != "index.json")
    for old in runs[:-KEEP_RUNS]:
        old.unlink()
    # The browser cannot list a folder on GitHub, so the run picker reads this index.
    _write(state_dir / "runs" / "index.json",
           {"schema_version": 1, "runs": [p.stem for p in runs[-KEEP_RUNS:]][::-1]})


def load_buffer(state_dir: Path) -> list[Item]:
    """Items from the hourly collector. Raises if the file exists but is invalid."""
    return load_buffer_full(state_dir).items


def load_buffer_full(state_dir: Path) -> RssBuffer:
    data = _read(state_dir / BUFFER_FILE)
    return RssBuffer.model_validate(data) if data else RssBuffer(
        schema_version=1, updated_at=datetime.min.replace(tzinfo=UTC), items=[])


def write_buffer(state_dir: Path, items: list[Item], now: datetime,
                 health: dict[str, dict] | None = None) -> None:
    """Only the collector calls this; the pipeline never writes the buffer, so the two
    workflows' commits touch different files and can always be rebased onto each other."""
    buf = RssBuffer(schema_version=1, updated_at=now, items=items, health=health or {})
    _write(state_dir / BUFFER_FILE, buf.model_dump(mode="json"))


def write_acled(state_dir: Path, records: list[dict], now: datetime) -> None:
    """acled.json: ACLED's last 30 days, replaced whole each run because ACLED revises past
    events. Called only after a successful fetch, so a failure keeps the previous file."""
    _write(state_dir / "acled.json", {"schema_version": 1, "fetched_at": now.isoformat(),
                                      "events": records})


BASELINE_DAYS = 120
PROCESSED_KEEP = 4 * 24 * 4  # four days of 15-minute GKG file stamps


def load_baselines(state_dir: Path) -> dict:
    return _read(state_dir / "baselines.json") or {"schema_version": 1,
                                                   "gkg": {"processed": [], "daily": {}}}


def merge_gkg(baselines: dict, records: list[dict], now: datetime) -> dict:
    """Add per-file counts to the daily totals, once per file; prune to 120 days."""
    gkg = baselines["gkg"]
    files = gkg.setdefault("files_per_day", {})
    done = set(gkg["processed"])
    for rec in records:
        if rec["file"] in done:
            continue
        done.add(rec["file"])
        fday = f"{rec['file'][:4]}-{rec['file'][4:6]}-{rec['file'][6:8]}"
        files[fday] = files.get(fday, 0) + 1
        for day, themes in rec["counts"].items():
            d = gkg["daily"].setdefault(day, {})
            for theme, countries in themes.items():
                t = d.setdefault(theme, {})
                for cc, n in countries.items():
                    t[cc] = t.get(cc, 0) + n
        # Summed tone, kept beside the counts: average tone = tone / count.
        for day, themes in rec.get("tone", {}).items():
            d = gkg.setdefault("tone", {}).setdefault(day, {})
            for theme, countries in themes.items():
                t = d.setdefault(theme, {})
                for cc, v in countries.items():
                    t[cc] = round(t.get(cc, 0.0) + v, 3)
    cutoff = (now - timedelta(days=BASELINE_DAYS)).strftime("%Y-%m-%d")
    gkg["daily"] = {k: v for k, v in sorted(gkg["daily"].items()) if k >= cutoff}
    gkg["files_per_day"] = {k: v for k, v in sorted(files.items()) if k >= cutoff}
    gkg["tone"] = {k: v for k, v in sorted(gkg.get("tone", {}).items()) if k >= cutoff}
    gkg["processed"] = sorted(done)[-PROCESSED_KEEP:]
    baselines["updated_at"] = now.isoformat()
    return baselines


def write_baselines(state_dir: Path, baselines: dict) -> None:
    _write(state_dir / "baselines.json", baselines)


CLASSIFIED_DAYS = 7


def load_classified(state_dir: Path) -> dict[str, dict]:
    """LLM labels from earlier runs, by item id, so an item is sent to the LLM only once."""
    return (_read(state_dir / "classified.json") or {}).get("items", {})


def write_classified(state_dir: Path, cache: dict[str, dict], now: datetime) -> None:
    cutoff = now - timedelta(days=CLASSIFIED_DAYS)
    kept = {k: v for k, v in cache.items() if datetime.fromisoformat(v["at"]) >= cutoff}
    _write(state_dir / "classified.json", {"schema_version": 1, "items": kept})


def load_events(state_dir: Path) -> list[Event]:
    data = _read(state_dir / "events.json")
    return [Event.model_validate(e) for e in data["events"]] if data else []


def write_events(state_dir: Path, events: list[Event]) -> None:
    _write(state_dir / "events.json",
           {"schema_version": 1, "events": [e.model_dump(mode="json") for e in events]})


def load_timeseries(state_dir: Path) -> list[dict]:
    data = _read(state_dir / "timeseries.json")
    return data["rows"] if data else []


def write_timeseries(state_dir: Path, rows: list[dict]) -> None:
    """Kept forever: about 300 KB a year at two runs a day."""
    _write(state_dir / "timeseries.json", {"schema_version": 1, "rows": rows, "sample": False})


def load_scoring_state(state_dir: Path) -> dict:
    """Per region: displayed level and index, runs below threshold (hysteresis); per anchor:
    level history (for the 'rose in 30 days' bonus)."""
    return _read(state_dir / "scoring_state.json") or {"regions": {}, "anchor_history": {}}


def write_scoring_state(state_dir: Path, scoring: dict) -> None:
    _write(state_dir / "scoring_state.json", scoring)
