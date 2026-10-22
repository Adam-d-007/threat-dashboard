"""Data shapes written to the data branch.

These pydantic models are the single source of truth: tools/export_schema.py
exports JSON Schema from them and the frontend generates its TypeScript types
from that schema. Adding an optional field is not breaking; anything else
bumps SCHEMA_VERSION.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1

Tier = Literal["A", "B", "C"]
SourceStatus = Literal["ok", "stale", "failed", "disabled"]
RunStatus = Literal["ok", "partial", "failed"]


class Strict(BaseModel):
    # Fields with defaults are always written, so the schema marks them required.
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class GdeltInfo(Strict):
    tone: float | None = None
    themes: list[str] = Field(default_factory=list)


class Item(Strict):
    id: str = Field(description="sha1 of the canonical URL")
    source_id: str
    tier: Tier
    url: str
    title: str
    lang: str
    published_at: datetime
    published_estimated: bool = Field(
        default=False,
        description="True when the source gave no date; published_at is then when the "
        "item was first seen",
    )
    fetched_at: datetime
    snippet: str = Field(max_length=300)
    domain: str
    also_reported_by: list[str] = Field(default_factory=list)
    gdelt: GdeltInfo | None = None


class SourceHealth(Strict):
    id: str
    name: str
    tier: Tier
    group: str
    status: SourceStatus
    last_success: datetime | None
    last_error: datetime | None = None
    items: int
    http_status: int | None = None
    error: str | None = None
    note: str | None = None


class RunCounts(Strict):
    fetched: int
    after_dedupe: int
    in_window: int


class RunInfo(Strict):
    id: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime
    window_start: datetime
    git_sha: str | None
    counts: RunCounts


class Run(Strict):
    schema_version: Literal[1]
    run: RunInfo
    sources: list[SourceHealth]
    items: list[Item]
