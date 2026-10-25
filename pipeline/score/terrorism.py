"""Terrorism level per region: components, LLM assessment, gates, disagreement, hysteresis and
smoothing. One RegionAssessment and one timeseries row per region per run."""

import json
import logging
from datetime import date, datetime, timedelta

from pydantic import ValidationError

from ..llm.client import LlmBadOutput, LlmClient, LlmUnavailable, ask
from ..llm.prompts import assess_system, assess_user
from ..llm.schemas import AssessmentOut
from ..models import AnchorReading, Driver, Event, LlmAssessment, OfficialLevel, RegionAssessment
from . import gates
from .components import (
    anchors_component,
    composite,
    event_contributions,
    events_component,
    level_of,
    llm_component,
    media_component,
)

log = logging.getLogger("pipeline.score")

MAX_PROMPT_EVENTS = 40


def _event_brief(e: Event, weight: float) -> dict:
    return {"id": e.id, "date": e.date.isoformat(), "country": e.country, "type": e.event_type,
            "ideology": e.ideology, "severity": e.severity, "sk_link": e.sk_link,
            "corroborated": e.corroborated, "sources": len(e.domains), "weight": round(weight, 3),
            "summary": e.title_en}


def assess_llm(region: str, client: LlmClient | None, contribs: list[tuple[Event, float]],
               anchors: list[AnchorReading], comps: dict, recent: list[dict],
               call_limit: int) -> LlmAssessment:
    """The LLM's reading of the region on the NBAC scale. Drivers citing unknown events are
    dropped. Any failure returns status 'fallback', and the score runs on rules alone."""
    if client is None or not client.providers:
        return LlmAssessment(status="disabled")
    if not client.available or client.calls >= call_limit:
        return LlmAssessment(status="fallback")
    events = [_event_brief(e, w) for e, w in contribs[:MAX_PROMPT_EVENTS]]
    known = {e["id"] for e in events}
    # National levels one by one; travel advice summarised, because 138 readings made the
    # prompt too large for Groq's free tier (HTTP 413 on 2026-10-22).
    anchor_rows: list[dict] = [{"country": a.country, "name": a.name, "value": a.raw,
                                "level": f"{a.level}/{len(a.scale)}"}
                               for a in anchors if a.raw and a.kind == "national"]
    travel = [a for a in anchors if a.raw and a.kind == "travel"
              and (region == "EU" or a.country == "SK")]
    by_gov: dict[str, dict[str, int]] = {}
    for a in travel:
        counts = by_gov.setdefault(f"{a.name} ({a.issuer})", {})
        counts[a.raw] = counts.get(a.raw, 0) + 1
    if by_gov:
        anchor_rows.append({"travel_advice_countries_per_value": by_gov})
    user = assess_user(region, events, anchor_rows, comps, recent)
    try:
        out = ask(client, assess_system(region), user,
                  lambda t: AssessmentOut.model_validate(json.loads(t)))
    except LlmUnavailable:
        return LlmAssessment(status="fallback")
    except (json.JSONDecodeError, ValidationError, LlmBadOutput) as e:
        log.warning("%s assessment failed: %s", region, str(e)[:200])
        return LlmAssessment(status="fallback")
    drivers = []
    for d in out.drivers:
        ids = [i for i in d.event_ids if i in known]
        if ids:
            drivers.append(Driver(text_en=d.text_en, text_sk=d.text_sk, event_ids=ids))
    return LlmAssessment(status="ok", level=out.level, position=out.position,
                         confidence=out.confidence, drivers=drivers,
                         what_changed_en=out.what_changed_en,
                         what_changed_sk=out.what_changed_sk, model=client.usage()["model"])


def disagree(llm_level: int, rules_level: int) -> bool:
    gap = abs(llm_level - rules_level)
    return gap >= 2 or (gap >= 1 and max(llm_level, rules_level) >= 3)


def score_region(region: str, run_id: str, events: list[Event], anchors: list[AnchorReading],
                 baselines: dict, rows: list[dict], scoring: dict, client: LlmClient | None,
                 now: datetime, cfg: dict, call_limit: int,
                 ) -> tuple[RegionAssessment | None, dict | None]:
    """Score one region. Returns (None, None) when no component has a value: the page then
    says the indicator is not computed, rather than showing an invented level."""
    contribs = event_contributions(events, region, now, cfg)
    window = (now - timedelta(days=cfg["events"]["baseline_days"])).isoformat()
    region_rows = [r for r in rows if r["region"] == region]
    history = [(r["at"], r["components"]["events_raw"]) for r in region_rows
               if r["at"] >= window and r["components"].get("events_raw") is not None]
    e_comp = events_component(contribs, history, region, cfg)
    m_comp = media_component(baselines, region, now, cfg)
    a_comp = anchors_component(anchors, region, scoring["anchor_history"], now, cfg)
    if composite([e_comp, m_comp, a_comp]) is None:
        log.warning("%s: no component has a value; no score this run", region)
        return None, None
    b = gates.bounds(region, events, now, cfg)

    p_rules = composite([e_comp, m_comp, a_comp]) or 0.0
    rules_level, rules_gates = gates.apply(level_of(p_rules, cfg), b)

    recent = [{"run": r["run_id"], "index": r["index"], "level": r["level"]}
              for r in region_rows[-3:]]
    comps = {"events": e_comp.value, "media": m_comp.value, "anchors": a_comp.value}
    llm = assess_llm(region, client, contribs, anchors, comps, recent, call_limit)
    l_comp = llm_component(llm, cfg)
    p = composite([e_comp, m_comp, a_comp, l_comp]) or 0.0
    raw_level = level_of(p, cfg)
    candidate, shown = gates.apply(raw_level, b)
    disagreement = llm.status == "ok" and disagree(llm.level, rules_level)
    if disagreement:
        # The level follows the rules, so the index does too: otherwise level 2 could show
        # with an index of 51, inside level 3's band (seen on 2026-10-23).
        candidate, shown = rules_level, rules_gates
        p = p_rules

    prev = scoring["regions"].get(region)
    level, below = candidate, 0
    # The brake (hysteresis) needs a settled baseline. While E is provisional there is none, and
    # the brake held levels that came from since-corrected labels three times on 2026-10-23,
    # so until then the level follows the current reading.
    provisional = e_comp.inputs.get("status") in ("warming_up", "provisional")
    if prev and candidate < prev["level"] and not provisional:
        # Down only after 4 runs in a row at least 0.03 below the current level's threshold.
        threshold = cfg["thresholds"][prev["level"] - 2]
        below = prev.get("below_runs", 0) + 1 if p <= threshold - cfg["hysteresis"]["margin"] \
            else 0
        if below < cfg["hysteresis"]["runs"]:
            level = prev["level"]
        else:
            below = 0
    level, shown = gates.apply(level, b) if level != candidate else (level, shown)

    raw_index = round(100 * p)
    # The displayed index is an EMA over runs. The raw value shows when a gate raised the level
    # (spec) and, extending the spec, whenever the level rose: otherwise a run could show level
    # 3 with an index of 48, outside level 3's band.
    gate_raised = raw_level < b.min_level
    rose = prev is not None and level > prev["level"]
    alpha = cfg["smoothing_alpha"]
    index = raw_index if (prev is None or gate_raised or rose) else \
        round(alpha * raw_index + (1 - alpha) * prev["index"])

    official = None
    if region == "SK":
        sis = next((a for a in anchors if a.id == "anchor_sk_sis" and a.level), None)
        if sis:
            official = OfficialLevel(source="SIS NBAC", level=sis.level, since=sis.since,
                                     checked_at=sis.as_of, url=sis.url,
                                     label_sk="zvýšený stupeň ohrozenia" if sis.level == 2
                                     else None)
    # Until E has its two weeks of history it is measured against the few days there are, so
    # the level is provisional: shown, but labelled as such.
    first = min((r["at"] for r in region_rows), default=now.isoformat())[:10]
    assessment = RegionAssessment(
        region=region, level=level, index=index, provisional=provisional,
        available_from=(date.fromisoformat(first)
                        + timedelta(days=cfg["events"]["min_history_days"]))
        if provisional else None,
        index_prev=prev["index"] if prev else None, level_prev=prev["level"] if prev else None,
        rules_level=rules_level, components=[e_comp, m_comp, a_comp, l_comp], gates=shown,
        llm=llm, disagreement=disagreement, official=official,
        anchor_ids=[a.id for a in anchors if a.id != "anchor_sk_sis"
                    and (region == "EU" or a.id in cfg["anchors"]["SK"]
                         or (a.kind == "travel" and a.country == "SK"))])
    row = {"run_id": run_id, "at": now.isoformat(), "region": region, "index": index,
           "level": level, "rules_level": rules_level,
           "llm_level": llm.level if llm.status == "ok" else None,
           "gates": [g.id for g in shown if g.id != "floor_eu_attack_30d"]
           + (["floor_eu_attack_30d"] if gate_raised else []),
           "components": {"events": e_comp.value, "media": m_comp.value,
                          "anchors": a_comp.value, "llm": l_comp.value,
                          "events_raw": e_comp.inputs["weighted_sum"], "p": round(p, 4),
                          "p_rules": round(p_rules, 4)}}
    scoring["regions"][region] = {"level": level, "index": index, "below_runs": below}
    log.info("%s: level %d (rules %d, llm %s), index %d (raw %d), gates %s", region, level,
             rules_level, llm.level, index, raw_index, [g.id for g in shown])
    return assessment, row


def update_anchor_history(scoring: dict, anchors: list[AnchorReading], now: datetime) -> None:
    """Append an anchor's level whenever it differs from the last one recorded."""
    hist = scoring.setdefault("anchor_history", {})
    day = now.strftime("%Y-%m-%d")
    for a in anchors:
        if a.level is None:
            continue
        h = hist.setdefault(a.id, [])
        if not h or h[-1][1] != a.level:
            h.append([day, a.level])
