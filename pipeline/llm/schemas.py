"""What the LLM must return for a classification batch. Validated with pydantic; anything
that does not fit is rejected, retried once with the error, then replaced by the rules."""

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
    model_config = ConfigDict(extra="ignore")
    items: list[ItemLabel]


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
