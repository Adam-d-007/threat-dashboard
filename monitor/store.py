"""Read and write the rebuilt pipeline's files: everything under v2/ of the data branch
(checked out at --state-dir). v2/state/ is its own memory between runs; the rest of v2/ is what
the website reads. Nothing outside v2/ is written, so the old pipeline's files are untouched.
A file that exists but does not validate raises: a run must not continue on a broken memory.
"""

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from .models import Article, Incident

ROOT = "v2"


def _read(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")


def public(state_dir: Path, name: str) -> Path:
    return state_dir / ROOT / name


def private(state_dir: Path, name: str) -> Path:
    return state_dir / ROOT / "state" / name


def load_articles(state_dir: Path) -> dict[str, Article]:
    data = _read(private(state_dir, "articles.json")) or {"articles": []}
    return {a["id"]: Article.model_validate(a) for a in data["articles"]}


def save_articles(state_dir: Path, articles: dict[str, Article], now: datetime) -> None:
    rows = sorted(articles.values(), key=lambda a: a.published_at, reverse=True)
    _write(private(state_dir, "articles.json"), {
        "schema_version": 2, "updated_at": now.isoformat(),
        "articles": [a.model_dump(mode="json") for a in rows]})


def load_incidents(state_dir: Path) -> list[Incident] | None:
    """None when the file does not exist yet (the first run then carries the old events over)."""
    data = _read(private(state_dir, "incidents.json"))
    return None if data is None else [Incident.model_validate(i) for i in data["incidents"]]


def save_incidents(state_dir: Path, incidents: list[Incident], removed: list[str],
                   now: datetime) -> None:
    _write(private(state_dir, "incidents.json"), {
        "schema_version": 2, "updated_at": now.isoformat(), "removed": removed,
        "incidents": [i.model_dump(mode="json") for i in incidents]})


def load_removed(state_dir: Path) -> list[str]:
    """Ids of incidents removed by hand, so they are not carried over or rebuilt."""
    return (_read(private(state_dir, "incidents.json")) or {}).get("removed", [])


def load_json(state_dir: Path, name: str, default):
    data = _read(private(state_dir, name))
    return default if data is None else data


def save_json(state_dir: Path, name: str, data) -> None:
    _write(private(state_dir, name), data)


def load_public(state_dir: Path, name: str):
    return _read(public(state_dir, name))


def write_public(state_dir: Path, name: str, model: BaseModel) -> None:
    """Validated again from its own dump, so a file the website cannot read is never written."""
    data = type(model).model_validate(model.model_dump()).model_dump(mode="json")
    _write(public(state_dir, name), data)
