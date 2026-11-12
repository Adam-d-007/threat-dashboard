"""Data shapes of the rebuilt pipeline: what it keeps between runs (articles, incidents) and
what it publishes for the website. Shapes the scoring and the website already use (Place,
RegionAssessment, AnchorReading, Theatre and so on) are the old pipeline's, unchanged.
"""

import datetime as dt
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pipeline.models import (
    AnchorReading,
    BriefLine,
    Diff,
    Gtd,
    Ideology,
    Place,
    SisAnnual,
    SkLink,
    SourceHealth,
    Terrorism,
    Tesat,
    Theatre,
    Tier,
    WatchlistEntry,
)

from .ai.labels import ArticleLabel, IncidentType

SCHEMA_VERSION = 2
Overall = Literal["ok", "degraded", "failed"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Article(Strict):
    """A news item worth showing to a model, with what became of it."""

    id: str = Field(description="sha1 of the canonical URL")
    source_id: str
    tier: Tier
    url: str
    title: str
    lang: str
    published_at: datetime
    fetched_at: datetime
    snippet: str
    domain: str
    also_reported_by: list[str] = Field(default_factory=list)
    first_seen: datetime
    label: ArticleLabel | None = None
    labelled_by: str | None = Field(default=None, description="The model that labelled it")
    labelled_at: datetime | None = None
    label_attempts: int = Field(default=0, description="Answers that left it out or mislabelled")
    place: Place | None = Field(default=None, description="incident_place with coordinates")
    incident_id: str | None = None
    matched_by: str | None = None
    match_attempts: int = 0
    given_up: str | None = Field(default=None, description="Why no model is asked again")


class Report(Strict):
    """An article on an incident's timeline."""

    article_id: str
    url: str
    source: str
    tier: Tier
    published_at: datetime
    kind: Literal["new_incident", "update"]
    summary_en: str | None = Field(description="None on reports carried over from the old "
                                   "pipeline, which kept no summary per article")
    summary_sk: str | None = None
    type: IncidentType = Field(description="What this report says the incident was")
    severity: int = Field(ge=1, le=5, description="How severe this report says it was")
    event_date: dt.date = Field(description="The day this report says it happened")
    also_reported_by: list[str] = Field(default_factory=list)


class Incident(Strict):
    id: str
    type: IncidentType
    severity: int = Field(ge=1, le=5)
    date: dt.date = Field(description="The day it happened, not the day it was reported")
    country: str
    place: Place | None = None
    ideology: Ideology
    sk_link: SkLink
    topic: Literal["terrorism", "hybrid"]
    title_en: str
    title_sk: str | None = None
    reports: list[Report] = Field(description="Its timeline, oldest first")
    domains: list[str] = Field(description="Outlets that reported it")
    has_tier_a: bool
    best_tier: Tier | None
    corroborated: bool
    first_seen: datetime
    last_updated: datetime
    seeded_from: str | None = Field(default=None, description="The old pipeline's event id, for "
                                    "incidents carried over at the start")


class Correction(Strict):
    action: Literal["merge", "remove", "detach"]
    note: str
    applied: bool


class IncidentsFile(Strict):
    """incidents/current.json and incidents/YYYY-MM.json."""

    schema_version: Literal[2]
    updated_at: datetime
    incidents: list[Incident]
    corrections: list[Correction] = Field(default_factory=list)


class ReportsFile(Strict):
    """reports.json: labelled, relevant articles of the last 48 hours."""

    schema_version: Literal[2]
    updated_at: datetime
    reports: list[Article]


class Summary(Strict):
    """summary.json: what the first screen needs."""

    schema_version: Literal[2]
    run_id: str | None = Field(description="The scoring run the levels come from")
    scored_at: datetime | None
    terrorism: Terrorism | None
    diff: Diff | None = Field(default=None, description="What changed between the last two "
                              "scoring runs")
    anchors: list[AnchorReading]
    tesat: Tesat | None = None
    sis_annual: SisAnnual | None = None
    gtd: Gtd | None = None


class TheatreV2(Theatre):
    lines: list[BriefLine] = Field(default_factory=list)
    written_at: datetime | None = Field(default=None, description="When this theatre's text "
                                        "was written; older than the run when a call failed")
    written_by: str | None = None


class GeopoliticsFile(Strict):
    schema_version: Literal[2]
    updated_at: datetime
    theatres: list[TheatreV2]
    watchlist: list[WatchlistEntry] = Field(default_factory=list)


class Stage(Strict):
    status: Overall | Literal["skipped"]
    detail: str


class Queue(Strict):
    waiting_label: int
    waiting_match: int
    oldest_waiting_hours: float | None
    given_up_24h: int
    labelled_24h: int


class Status(Strict):
    """status.json: what each stage did, in facts rather than one word."""

    schema_version: Literal[2]
    updated_at: datetime
    started_at: datetime
    git_sha: str | None
    overall: Overall
    reasons: list[str]
    stages: dict[str, Stage]
    queue: Queue
    ai: dict[str, dict]
    labelled_by_24h: dict[str, int] = Field(description="Articles labelled per model, 24 hours")
    last_scored: str | None
    brief_written_at: datetime | None
    sources: list[SourceHealth]
