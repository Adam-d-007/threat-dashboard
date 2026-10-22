"""Read and write the files on the data branch (checked out at --state-dir)."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from ..models import Item, RssBuffer, Run, SourceHealth

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
    runs = sorted((state_dir / "runs").glob("*.json"))
    for old in runs[:-KEEP_RUNS]:
        old.unlink()


def load_buffer(state_dir: Path) -> list[Item]:
    """Items from the hourly RSS collector. Raises if the file exists but is invalid."""
    data = _read(state_dir / BUFFER_FILE)
    return RssBuffer.model_validate(data).items if data else []


def write_buffer(state_dir: Path, items: list[Item], now: datetime) -> None:
    """Only the collector calls this; the pipeline never writes the buffer, so the two
    workflows' commits touch different files and can always be rebased onto each other."""
    buf = RssBuffer(schema_version=1, updated_at=now, items=items)
    _write(state_dir / BUFFER_FILE, buf.model_dump(mode="json"))


def write_acled(state_dir: Path, records: list[dict], now: datetime) -> None:
    """acled.json: ACLED's last 30 days, replaced whole each run because ACLED revises past
    events. Called only after a successful fetch, so a failure keeps the previous file."""
    _write(state_dir / "acled.json", {"schema_version": 1, "fetched_at": now.isoformat(),
                                      "events": records})
