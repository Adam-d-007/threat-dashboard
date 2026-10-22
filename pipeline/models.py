"""Data shapes written to the data branch.

These pydantic models are the single source of truth: tools/export_schema.py
exports JSON Schema from them and the frontend generates its TypeScript types
from that schema. Adding an optional field is not breaking; anything else
bumps SCHEMA_VERSION.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1

Tier = Literal["A", "B", "C"]
SourceStatus = Literal["ok", "stale", "failed", "disabled"]
RunStatus = Literal["ok", "partial", "failed"]
Region = Literal["SK", "EU"]
Level = Literal[1, 2, 3, 4]
Domain = Literal["terrorism", "hybrid", "cyber", "unrest", "geopolitics", "other"]
EventType = Literal["attack", "attempted_attack", "plot_disrupted", "arrest", "conviction",
                    "threat_statement", "sabotage", "other"]
# Europol TE-SAT categories, plus state_linked for sabotage and attacks attributed to a state.
Ideology = Literal["jihadist", "right_wing", "left_anarchist", "ethno_separatist", "state_linked",
                   "other", "unknown"]
SkLink = Literal["none", "indirect", "direct"]
Precision = Literal["city", "region", "country"]


class Strict(BaseModel):
    # Fields with defaults are always written, so the schema marks them required.
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class GdeltInfo(Strict):
    tone: float | None = None
    themes: list[str] = Field(default_factory=list)


class Place(Strict):
    name: str
    lat: float
    lon: float
    precision: Precision


class Classification(Strict):
    status: Literal["llm", "rules", "unclassified"]
    relevant: bool
    domain: Domain
    event_type: EventType
    ideology: Ideology
    severity: int = Field(ge=0, le=5, description="0 not an incident, 1 arrest or disrupted "
                          "plot, 2 attempted attack, 3 attack without deaths, 4 attack with 1 to "
                          "4 deaths, 5 attack with 5 or more deaths")
    sk_link: SkLink
    countries: list[str] = Field(default_factory=list, description="ISO 3166-1 alpha-2")
    places: list[Place] = Field(default_factory=list)
    event_key: str | None = None
    summary_en: str | None = None
    summary_sk: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


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
    classification: Classification | None = None
    event_id: str | None = None


class Event(Strict):
    id: str
    title_en: str
    title_sk: str | None = None
    event_type: EventType
    ideology: Ideology
    severity: int = Field(ge=0, le=5)
    date: date
    country: str
    place: Place | None = None
    sk_link: SkLink
    item_ids: list[str]
    domains: list[str]
    has_tier_a: bool
    corroborated: bool
    first_seen: datetime
    last_updated: datetime


class AnchorReading(Strict):
    """An official threat level read from a government page, or FCDO travel-advice wording."""

    id: str
    country: str = Field(description="ISO 3166-1 alpha-2")
    name: str
    url: str
    scale: list[str] = Field(description="Allowed raw values, lowest to highest")
    raw: str | None = Field(description="Value read from the page, one of scale")
    level: int | None = Field(description="1-based position of raw on scale")
    normalized: float | None = Field(description="(level - 1) / (len(scale) - 1)")
    since: date | None = Field(default=None, description="Date the level was declared, if stated")
    as_of: datetime | None = Field(description="Last time the value was read successfully")
    status: SourceStatus
    error: str | None = None
    text_hash: str | None = Field(default=None, description="sha1 of the paragraph stating the "
                                  "level, to detect any change in wording")
    detail: str | None = Field(default=None, description="Other levels in force at the same "
                               "time, e.g. a higher level for railways only")
    manual: bool = Field(default=False, description="Typed in by hand from the official page, "
                         "because the page cannot be read automatically")


class Component(Strict):
    id: Literal["events", "media", "anchors", "llm"]
    weight: float
    value: float | None = Field(ge=0, le=1)
    inputs: dict[str, float | int | str | None] = Field(default_factory=dict)
    event_ids: list[str] = Field(default_factory=list)


class Gate(Strict):
    id: str
    effect: str
    event_ids: list[str] = Field(default_factory=list)


class Driver(Strict):
    text_en: str
    text_sk: str | None = None
    event_ids: list[str]


class LlmAssessment(Strict):
    status: Literal["ok", "fallback", "disabled"]
    level: Level | None = None
    position: Literal["low", "mid", "high"] | None = None
    confidence: Literal["low", "medium", "high"] | None = None
    drivers: list[Driver] = Field(default_factory=list)
    what_changed_en: str | None = None
    what_changed_sk: str | None = None
    model: str | None = None


class OfficialLevel(Strict):
    source: str
    level: int
    label_sk: str | None = None
    since: date | None = None
    checked_at: datetime | None = None
    url: str


class RegionAssessment(Strict):
    region: Region
    level: Level
    index: int = Field(ge=0, le=100)
    index_prev: int | None = None
    level_prev: Level | None = None
    rules_level: Level
    components: list[Component]
    gates: list[Gate] = Field(default_factory=list)
    llm: LlmAssessment
    disagreement: bool
    official: OfficialLevel | None = Field(default=None, description="SIS level for SK; "
                                           "none for the EU, which has no EU-wide level")
    anchor_ids: list[str] = Field(default_factory=list)


class Terrorism(Strict):
    SK: RegionAssessment
    EU: RegionAssessment


class Activity(Strict):
    value: float | None = Field(ge=0, le=1, description="f(articles 24 h / 90-day median)")
    articles_24h: int | None = None
    baseline_median: float | None = None


class AcledActivity(Strict):
    events_7d: int
    avg_week_prev_4: float


class Tone(Strict):
    value: float
    baseline_median: float


class TopItem(Strict):
    item_id: str
    summary_en: str
    summary_sk: str | None = None


class Theatre(Strict):
    id: str
    name_en: str
    name_sk: str
    activity: Activity
    acled: AcledActivity | None = None
    tone: Tone | None = None
    sparkline: list[float] = Field(default_factory=list, description="Activity value per day, "
                                   "oldest first, up to 30 days")
    top_items: list[TopItem] = Field(default_factory=list)
    sk_angle_en: str | None = None
    sk_angle_sk: str | None = None


class BriefLine(Strict):
    text_en: str
    text_sk: str | None = None
    item_ids: list[str]


class Brief(Strict):
    status: Literal["ok", "fallback", "disabled"]
    lines: list[BriefLine] = Field(default_factory=list)
    what_changed_en: str | None = None
    what_changed_sk: str | None = None


class WatchlistEntry(Strict):
    date: date
    title_en: str
    title_sk: str | None = None
    origin: Literal["manual", "news"]
    verified: bool
    url: str | None = None


class Geopolitics(Strict):
    theatres: list[Theatre]
    brief: Brief | None = None
    watchlist: list[WatchlistEntry] = Field(default_factory=list)


class LevelChange(Strict):
    region: Region
    level_from: int | None
    level_to: int


class ValueChange(Strict):
    id: str
    value_from: str | None
    value_to: str | None


class Diff(Strict):
    new_event_ids: list[str] = Field(default_factory=list)
    level_changes: list[LevelChange] = Field(default_factory=list)
    anchor_changes: list[ValueChange] = Field(default_factory=list)
    source_changes: list[ValueChange] = Field(default_factory=list)


class TesatYear(Strict):
    data_year: int
    attacks_total: int
    attacks_completed: int | None = None
    member_states_with_attacks: int | None = None
    fatalities: int | None = None
    arrests_total: int


class Tesat(Strict):
    """Europol TE-SAT yearly figures, typed in from the PDF (manual_anchors.yaml)."""

    report_year: int
    url: str
    current: TesatYear
    attacks_failed: int
    attacks_foiled: int
    attacks_by_ideology: dict[str, int]
    arrests_by_ideology: dict[str, int]
    slovakia_attacks: int
    slovakia_arrests: int
    previous: TesatYear | None = None


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
    from_buffer: int = Field(description="Items read from the hourly RSS collector's buffer")
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
    anchors: list[AnchorReading] = Field(default_factory=list)
    terrorism: Terrorism | None = Field(default=None, description="Null until scoring exists")
    geopolitics: Geopolitics | None = None
    events: list[Event] = Field(default_factory=list, description="Events from the last 30 days")
    diff: Diff | None = None
    tesat: Tesat | None = None
    sample: bool = Field(default=False, description="True for made-up sample data used to "
                         "develop the frontend; the site labels it on every page")


class RssBuffer(Strict):
    """rss_buffer.json: items the hourly collector found in the last 48 h."""

    schema_version: Literal[1]
    updated_at: datetime
    items: list[Item]


class TimeseriesRow(Strict):
    run_id: str
    at: datetime
    region: Region
    index: int
    level: Level
    rules_level: Level
    llm_level: Level | None
    components: dict[str, float | None]


class Timeseries(Strict):
    """timeseries.json: one row per region per run, never pruned."""

    schema_version: Literal[1]
    rows: list[TimeseriesRow]
    sample: bool = False
