"""Stage 5, scoring: twice a day, with the old pipeline's method unchanged (components E, M, A
and L, gates, smoothing, the brake on falling levels; pipeline/score and docs/SCORING.md).
What changes is what goes in: incidents instead of every relevant article, dated when they
happened, and a model assessment asked through the strict AI layer.
"""

import logging
from datetime import datetime

from pipeline.llm.prompts import assess_system
from pipeline.models import AnchorReading, LlmAssessment, Terrorism
from pipeline.score.terrorism import (
    assess_prompt,
    assessment_of,
    score_region,
    update_anchor_history,
)

from .ai.client import AiUnavailable
from .ai.tasks import ASSESS_SCHEMA, parse_assessment
from .incidents import to_event
from .models import Incident

log = logging.getLogger("monitor.score")


def due_slot(now: datetime, slots: dict[str, int], rows: list[dict]) -> str | None:
    """The run id of the scoring slot to run now ("2026-11-12T13"), or None. A slot may run
    from its hour (UTC) on and runs once; a run that comes late still scores the day's latest
    slot, so an hour GitHub skipped costs nothing."""
    for name in sorted(slots, reverse=True):
        if now.hour >= slots[name]:
            run_id = now.strftime("%Y-%m-%dT") + name
            return None if any(r["run_id"] == run_id for r in rows) else run_id
    return None


def assessor(ai, max_events: int):
    """The model's reading of a region, in the form score_region asks for it. No model
    answering gives status 'fallback': the level then rests on the other three components."""
    def assess(region, _client, contribs, anchors, comps, recent, _limit) -> LlmAssessment:
        if ai is None:
            return LlmAssessment(status="disabled")
        user, known = assess_prompt(region, contribs, anchors, comps, recent, max_events)
        try:
            out, model = ai.ask("assess", assess_system(region), user, ASSESS_SCHEMA,
                                "assessment", parse_assessment)
        except AiUnavailable as e:
            log.warning("%s assessment failed: %s", region, e)
            return LlmAssessment(status="fallback")
        return assessment_of(out, known, ai.models[model].model)
    return assess


def score(run_id: str, incidents: list[Incident], anchors: list[AnchorReading],
          baselines: dict, rows: list[dict], scoring: dict, ai, now: datetime, cfg: dict,
          max_events: int) -> Terrorism | None:
    """Score both regions; appends their rows to rows and updates scoring in place. None when
    a region has no component with a value."""
    events = [to_event(i) for i in incidents]
    update_anchor_history(scoring, anchors, now)
    regions = {}
    for region in ("SK", "EU"):
        regions[region], row = score_region(region, run_id, events, anchors, baselines, rows,
                                            scoring, None, now, cfg, 0,
                                            assess=assessor(ai, max_events))
        if row:
            rows.append(row)
    if not all(regions.values()):
        return None
    return Terrorism(SK=regions["SK"], EU=regions["EU"])
