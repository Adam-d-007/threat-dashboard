"""What the LLM must return: classification batches, assessments and the brief. Validated with
pydantic; an answer that does not fit is rejected and asked again (llm.client.ask), then the
rules take over. A batch's labels are checked one by one (process.classify)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..models import Domain, EventType, Ideology, SkLink


class PlaceRef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=100)
    country: str = Field(pattern=r"^[A-Z]{2}$")


class ItemLabel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    relevant: bool
    domain: Domain
    event_type: EventType
    ideology: Ideology
    severity: int = Field(ge=0, le=5)
    sk_link: SkLink
    countries: list[str] = Field(default_factory=list, max_length=6)
    places: list[PlaceRef] = Field(default_factory=list, max_length=4)
    event_key: str | None = Field(default=None, max_length=160)
    summary_en: str = Field(max_length=400)
    summary_sk: str = Field(max_length=400)
    confidence: float = Field(ge=0, le=1)


class Batch(BaseModel):
    """Items are validated one by one (classify._labels): one malformed label must not throw
    away the other eleven (Groq left out summary_en for single items on 2026-10-27)."""
    model_config = ConfigDict(extra="ignore")
    items: list[dict]


class DriverOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text_en: str = Field(max_length=400)
    text_sk: str = Field(max_length=400)
    event_ids: list[str] = Field(default_factory=list, max_length=10)


class AssessmentOut(BaseModel):
    """What the LLM returns for one region's assessment."""

    model_config = ConfigDict(extra="ignore")
    level: int = Field(ge=1, le=4)
    position: Literal["low", "mid", "high"]
    confidence: Literal["low", "medium", "high"]
    drivers: list[DriverOut] = Field(default_factory=list, max_length=5)
    what_changed_en: str = Field(max_length=600)
    what_changed_sk: str = Field(max_length=600)


class BriefLineOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text_en: str = Field(max_length=500)
    text_sk: str = Field(max_length=500)
    item_ids: list[str] = Field(default_factory=list, max_length=6)


class TopItemOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    item_id: str
    summary_en: str = Field(max_length=400)
    summary_sk: str = Field(max_length=400)


class TheatreOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    top_items: list[TopItemOut] = Field(default_factory=list, max_length=5)
    sk_angle_en: str | None = Field(default=None, max_length=400)
    sk_angle_sk: str | None = Field(default=None, max_length=400)


class DateOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    title_en: str = Field(max_length=200)
    title_sk: str = Field(max_length=200)
    item_id: str


class BriefOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    lines: list[BriefLineOut] = Field(max_length=8)
    # Optional: Groq's model left both out twice on 2026-10-25; the page omits the paragraph.
    what_changed_en: str | None = Field(default=None, max_length=600)
    what_changed_sk: str | None = Field(default=None, max_length=600)
    theatres: list[TheatreOut] = Field(default_factory=list)
    upcoming: list[DateOut] = Field(default_factory=list, max_length=10)
