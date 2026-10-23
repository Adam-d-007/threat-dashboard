"""Gates written from the NBAC level definitions. They bound the level that P may reach.

- floor_eu_attack_30d (SK and EU): a corroborated attack (or attempt) of severity 2 or more in
  an EU or NATO state in the last 30 days sets the level to at least 2.
- cap_sk_2: level 3 for Slovakia needs a corroborated event with a direct Slovak link in 30
  days, or a corroborated attack of severity 3+ in the EU or NATO in 14 days with sk_link at
  least indirect.
- cap_sk_3: level 4 for Slovakia needs a corroborated direct-link attack, attempt or disrupted
  plot within 72 hours with at least one Tier A source.
- cap_eu_3: level 4 for the EU needs a severity 5 attack in the EU in 7 days, or 3 attacks of
  severity 3+ in at least 2 member states in 7 days.
The official SIS level is not a floor: the indicator may sit above or below it.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..models import Event, Gate
from .components import EU27, EU_NATO

ATTACKS = {"attack", "attempted_attack"}


@dataclass
class Bounds:
    min_level: int = 1
    max_level: int = 4
    floor: Gate | None = None
    caps: list[Gate] = field(default_factory=list)


def _since(e: Event, now: datetime, days: float) -> bool:
    return e.date >= (now - timedelta(days=days)).date()


def bounds(region: str, events: list[Event], now: datetime, cfg: dict) -> Bounds:
    g = cfg["gates"]
    b = Bounds()
    floor = [e for e in events if e.corroborated and e.event_type in ATTACKS
             and e.severity >= 2 and e.country in EU_NATO
             and _since(e, now, g["floor_attack_days"])]
    if floor:
        b.min_level = 2
        b.floor = Gate(id="floor_eu_attack_30d", effect="min_level 2",
                       event_ids=[e.id for e in floor][:20])
    if region == "SK":
        direct = [e for e in events if e.corroborated and e.sk_link == "direct"
                  and _since(e, now, g["sk_cap2_direct_days"])]
        near = [e for e in events if e.corroborated and e.event_type in ATTACKS
                and e.severity >= 3 and e.country in EU_NATO and e.sk_link != "none"
                and _since(e, now, g["sk_cap2_attack_days"])]
        if not (direct or near):
            b.max_level = 2
            b.caps.append(Gate(id="cap_sk_2", effect="max_level 2"))
        imminent = [e for e in events if e.corroborated and e.sk_link == "direct"
                    and e.event_type in ATTACKS | {"plot_disrupted"} and e.has_tier_a
                    and _since(e, now, g["sk_cap3_hours"] / 24)]
        if not imminent:
            b.max_level = min(b.max_level, 3)
            b.caps.append(Gate(id="cap_sk_3", effect="max_level 3"))
    else:
        week = [e for e in events if e.corroborated and e.event_type in ATTACKS
                and e.country in EU27 and _since(e, now, g["eu_cap3_days"])]
        mass = [e for e in week if e.severity >= 5]
        wave = [e for e in week if e.severity >= 3]
        if not (mass or (len(wave) >= 3 and len({e.country for e in wave}) >= 2)):
            b.max_level = 3
            b.caps.append(Gate(id="cap_eu_3", effect="max_level 3"))
    return b


def apply(level: int, b: Bounds) -> tuple[int, list[Gate]]:
    """Bound a level. Returns (bounded level, gates to show): the floor whenever it holds, a cap
    only when it actually lowered the level."""
    shown = [b.floor] if b.floor else []
    bounded = level
    for cap in sorted(b.caps, key=lambda c: int(c.effect.split()[-1])):
        cap_level = int(cap.effect.split()[-1])
        if bounded > cap_level:
            bounded = cap_level
            shown.append(cap)
    return max(bounded, b.min_level), shown
