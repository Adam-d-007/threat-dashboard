"""Score components E (events), M (media), A (official levels) and L (LLM), the shared curve,
and the composite P. Pure functions: everything they need is passed in, so they test easily.
A component that cannot be computed honestly (no baseline yet, no data) has value None and is
left out of P, whose weights are then rescaled to sum to 1, as the spec does for a failed LLM."""

import math
from datetime import datetime, timedelta
from itertools import pairwise
from statistics import median

from ..models import AnchorReading, Component, Event, LlmAssessment

EU27 = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE",
        "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"}


def curve(r: float, cfg: dict) -> float:
    """f(r) = 1 - 0.625^r, r capped at 5: 0.375 at the baseline, ~0.61 at twice, ~0.76 at 3x."""
    return 1 - cfg["curve"]["base"] ** min(max(r, 0.0), cfg["curve"]["r_cap"])


def proximity(e: Event, region: str, cfg: dict) -> float:
    p = cfg["proximity"][region]
    if region == "SK":
        if e.country == "SK":
            return p["self"]
        if e.country in p["neighbours"]["countries"]:
            return p["neighbours"]["value"]
        if e.country in EU27:
            return p["eu"]
        return p["outside_eu_direct"] if e.sk_link == "direct" else 0.0
    if e.country in EU27:
        return p["member"]
    return p["near"]["value"] if e.country in p["near"]["countries"] else 0.0


def corroboration(e: Event, cfg: dict) -> float:
    c = cfg["events"]["corroboration"]
    if e.corroborated:
        return c["corroborated"]
    return c.get(e.best_tier or "B", c["B"])


def event_contributions(events: list[Event], region: str, now: datetime,
                        cfg: dict) -> list[tuple[Event, float]]:
    """(event, s * p * c * e^(-age/10)) for events in the 60-day window, largest first."""
    ec = cfg["events"]
    out = []
    for e in events:
        age = (now.date() - e.date).days
        if age < 0 or age > ec["window_days"]:
            continue
        w = (ec["severity_weight"][e.severity] * proximity(e, region, cfg)
             * corroboration(e, cfg) * math.exp(-age / ec["decay_days"]))
        if w > 0:
            out.append((e, w))
    return sorted(out, key=lambda x: -x[1])


def events_component(contribs: list[tuple[Event, float]], history: list[tuple[str, float]],
                     region: str, cfg: dict) -> Component:
    """history: (run time, E_raw) of earlier runs in the 180-day baseline window. Warm-up counts
    distinct days, so a burst of manual runs cannot fake two weeks of history. During warm-up
    E is compared with the median of the days there are (status 'provisional'); it is only
    empty when there is no earlier run at all."""
    ec = cfg["events"]
    raw = round(sum(w for _, w in contribs), 3)
    days = len({at[:10] for at, _ in history})
    inputs: dict = {"weighted_sum": raw, "events": len(contribs), "history_days": days,
                    "floor": ec["floor"][region]}
    ids = [e.id for e, _ in contribs[:10]]
    if not history:
        inputs["status"] = "warming_up"
        return Component(id="events", weight=cfg["weights"]["events"], value=None,
                         inputs=inputs, event_ids=ids)
    if days < ec["min_history_days"]:
        inputs["status"] = "provisional"
    base = median(v for _, v in history)
    r = raw / max(base, ec["floor"][region])
    inputs |= {"baseline_median": round(base, 3), "ratio": round(r, 3)}
    return Component(id="events", weight=cfg["weights"]["events"],
                     value=round(curve(r, cfg), 4), inputs=inputs, event_ids=ids)


def media_component(baselines: dict, region: str, now: datetime, cfg: dict) -> Component:
    """Articles with the TERROR theme mentioning the region on the latest complete day,
    against the median of the complete days in the 90 days before it."""
    mc = cfg["media"]
    gkg = baselines.get("gkg", {})
    files = gkg.get("files_per_day", {})
    today = now.strftime("%Y-%m-%d")
    complete = sorted(d for d, n in files.items() if n >= mc["min_files_per_day"] and d < today)
    key = mc["key"][region]

    def count(day: str) -> int:
        return gkg.get("daily", {}).get(day, {}).get(mc["theme"], {}).get(key, 0)

    weight = cfg["weights"]["media"]
    if not complete:
        return Component(id="media", weight=weight, value=None,
                         inputs={"status": "warming_up", "complete_days": 0})
    latest = complete[-1]
    start = (datetime.fromisoformat(latest) - timedelta(days=mc["baseline_days"])).strftime(
        "%Y-%m-%d")
    history = [count(d) for d in complete[:-1] if d >= start]
    inputs: dict = {"day": latest, "articles": count(latest), "complete_days": len(history),
                    "floor": mc["floor"][region]}
    if len(history) < mc["min_history_days"]:
        inputs["status"] = "warming_up"
        return Component(id="media", weight=weight, value=None, inputs=inputs)
    base = median(history)
    r = count(latest) / max(base, mc["floor"][region])
    inputs |= {"baseline_median": base, "ratio": round(r, 3)}
    return Component(id="media", weight=weight, value=round(curve(r, cfg), 4), inputs=inputs)


def anchor_rose(history: dict, ids: list[str], now: datetime, days: int) -> list[str]:
    """Anchors whose level went up within the last `days` days."""
    since = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    rose = []
    for aid in ids:
        h = history.get(aid, [])
        if any(day >= since and lvl > prev for (_, prev), (day, lvl) in pairwise(h)):
            rose.append(aid)
    return rose


def anchors_component(anchors: list[AnchorReading], region: str, history: dict, now: datetime,
                      cfg: dict) -> Component:
    ac = cfg["anchors"]
    by_id = {a.id: a for a in anchors if a.normalized is not None}
    weight = cfg["weights"]["anchors"]
    # Travel advice: every government's reading for the region's countries, averaged.
    travel = [a for a in by_id.values() if a.kind == "travel"
              and (a.country == "SK" if region == "SK" else True)]
    travel_mean = sum(a.normalized for a in travel) / len(travel) if travel else None
    if region == "SK":
        used = {aid: w for aid, w in ac["SK"].items() if aid in by_id}
        parts = [(by_id[a].normalized, w) for a, w in used.items()]
        ids = list(used) + [a.id for a in travel]
        inputs: dict = {aid: by_id[aid].normalized for aid in used}
        travel_weight = ac["SK_travel_weight"]
    else:
        nat = [by_id[a].normalized for a in ac["EU"]["national"] if a in by_id]
        parts = [(sum(nat) / len(nat), ac["EU"]["national_weight"])] if nat else []
        ids = [a for a in ac["EU"]["national"] if a in by_id] + [a.id for a in travel]
        inputs = {"national_mean": round(sum(nat) / len(nat), 3) if nat else None,
                  "national_levels": len(nat)}
        travel_weight = ac["EU"]["travel_weight"]
    if travel_mean is not None:
        parts.append((travel_mean, travel_weight))
    inputs |= {"travel_mean": round(travel_mean, 3) if travel_mean is not None else None,
               "travel_readings": len(travel),
               "travel_governments": len({a.issuer for a in travel})}
    total = sum(w for _, w in parts)
    value = sum(v * w for v, w in parts) / total if total else None
    if value is None:
        return Component(id="anchors", weight=weight, value=None, inputs={"status": "no_data"})
    rose = anchor_rose(history, ids, now, ac["rise_days"])
    if rose:
        value = min(1.0, value + ac["rise_bonus"])
    inputs["rose_30d"] = ", ".join(rose) or None
    return Component(id="anchors", weight=weight, value=round(value, 4), inputs=inputs)


def llm_component(a: LlmAssessment | None, cfg: dict) -> Component:
    weight = cfg["weights"]["llm"]
    if a is None or a.status != "ok" or a.level is None or a.position is None:
        return Component(id="llm", weight=weight, value=None,
                         inputs={"status": a.status if a else "disabled"})
    pos = cfg["llm_position"][a.position]
    return Component(id="llm", weight=weight, value=round((a.level - 1 + pos) / 4, 4),
                     inputs={"level": a.level, "position": a.position,
                             "confidence": a.confidence})


def composite(components: list[Component]) -> float | None:
    """P with the weights of the components that have a value rescaled to sum to 1."""
    used = [c for c in components if c.value is not None]
    total = sum(c.weight for c in used)
    return sum(c.weight * c.value for c in used) / total if total else None


def level_of(p: float, cfg: dict) -> int:
    return 1 + sum(p >= t for t in cfg["thresholds"])
