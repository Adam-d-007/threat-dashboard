"""Stage 8, events: reports of the same incident become one event.

An item joins an event when they share an LLM event_key, or have the same event type and
country, dates within one day (seven for severe attacks), and either places within 50 km or,
when one side has no place, clearly similar English summaries (token_sort_ratio >= 66; measured
2026-10-22: two reports of one arrest scored 70, a different arrest in the same country 60).
Only terrorism and hybrid reports make events: unrest (riots, protest arrests) is not a
terrorism incident, and on 2026-10-26 it filled the incident table and raised the EU to level 3
with protests in France, Spain and Portugal. Events persist in
events.json for 90 days, so a story covered over several days stays one event. An event is
corroborated with two or more independent domains, or one Tier A source. Unclassified items
never enter."""

import hashlib
import math
from datetime import datetime, timedelta

from rapidfuzz import fuzz

from ..models import Event, Item, Place
from .prefilter import fold

DOMAINS = {"terrorism", "hybrid"}
MAX_KM = 50
MAX_DAYS = 1
SUMMARY_MIN = 66
# Severe attacks (severity 3+) are rare: two of the same type in one country within a day are
# treated as one incident unless both have towns more than MAX_KM apart. On 2026-10-23 one
# shooting near Paris, reported with differing wording and mostly no town, became six events.
# Follow-up reports of a severe attack (arrests, the motive, the victims) come for days and are
# dated when published: within SEVERE_DAYS they join it. On 2026-10-26 the Jordan church
# shooting of 10-23 came back as a new attack, and the Trappes shooting of 10-23 as a
# "racist attack in Paris" on 10-25.
SEVERE = 3
SEVERE_DAYS = 7
KEEP_DAYS = 90
SK_RANK = {"none": 0, "indirect": 1, "direct": 2}
TIER_RANK = {"A": 0, "B": 1, "C": 2}


def _best(a: str | None, b: str | None) -> str | None:
    return min((t for t in (a, b) if t), key=TIER_RANK.get, default=None)


def km(a: Place, b: Place) -> float:
    """Great-circle distance (haversine)."""
    la1, lo1, la2, lo2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(h))


def eligible(item: Item) -> bool:
    c = item.classification
    return bool(c and c.status != "unclassified" and c.relevant and c.domain in DOMAINS
                and c.countries)


def _matches(item: Item, e: Event) -> bool:
    c = item.classification
    if c.event_key and c.event_key in e.event_keys:
        return True
    if c.event_type != e.event_type or c.countries[0] != e.country:
        return False
    severe = c.severity >= SEVERE and e.severity >= SEVERE
    if abs((item.published_at.date() - e.date).days) > (SEVERE_DAYS if severe else MAX_DAYS):
        return False
    place = c.places[0] if c.places else None
    if place and e.place and place.precision == "city" and e.place.precision == "city":
        return km(place, e.place) <= MAX_KM
    if severe:
        return True
    return bool(c.summary_en) and fuzz.token_sort_ratio(
        fold(c.summary_en), fold(e.title_en)) >= SUMMARY_MIN


def _same_incident(a: Event, b: Event) -> bool:
    """The item rule, applied between two stored events."""
    if set(a.event_keys) & set(b.event_keys):
        return True
    if a.event_type != b.event_type or a.country != b.country:
        return False
    severe = a.severity >= SEVERE and b.severity >= SEVERE
    if abs((a.date - b.date).days) > (SEVERE_DAYS if severe else MAX_DAYS):
        return False
    if a.place and b.place and a.place.precision == "city" and b.place.precision == "city":
        return km(a.place, b.place) <= MAX_KM
    if severe:
        return True
    return fuzz.token_sort_ratio(fold(a.title_en), fold(b.title_en)) >= SUMMARY_MIN


def _absorb(keep: Event, gone: Event) -> None:
    for attr in ("item_ids", "urls", "event_keys", "domains"):
        target = getattr(keep, attr)
        target.extend(x for x in getattr(gone, attr) if x not in target)
    keep.has_tier_a = keep.has_tier_a or gone.has_tier_a
    keep.best_tier = _best(keep.best_tier, gone.best_tier)
    keep.corroborated = keep.has_tier_a or len(keep.domains) >= 2
    keep.severity = max(keep.severity, gone.severity)
    if gone.topic == "terrorism":
        keep.topic = "terrorism"
    if keep.ideology == "unknown":
        keep.ideology = gone.ideology
    if SK_RANK[gone.sk_link] > SK_RANK[keep.sk_link]:
        keep.sk_link = gone.sk_link
    if gone.place and (keep.place is None
                       or (keep.place.precision != "city" and gone.place.precision == "city")):
        keep.place = gone.place
    keep.date = min(keep.date, gone.date)
    keep.first_seen = min(keep.first_seen, gone.first_seen)
    keep.last_updated = max(keep.last_updated, gone.last_updated)


def merge_events(events: list[Event], now: datetime) -> tuple[list[Event], dict[str, str]]:
    """Merge recent events that turn out to be one incident (an earlier split, or a later
    report bridging two halves). Returns (events, {merged id: kept id})."""
    recent_from = (now - timedelta(days=7)).date()
    merged: dict[str, str] = {}
    kept: list[Event] = []
    for e in sorted(events, key=lambda e: e.first_seen):
        target = next((k for k in kept if k.date >= recent_from and e.date >= recent_from
                       and _same_incident(k, e)), None)
        if target:
            _absorb(target, e)
            merged[e.id] = target.id
        else:
            kept.append(e)
    return kept, merged


def _new_event(item: Item, now: datetime) -> Event:
    c = item.classification
    return Event(
        id="evt_" + hashlib.sha1(item.id.encode()).hexdigest()[:12],
        title_en=c.summary_en or item.title, title_sk=c.summary_sk,
        event_type=c.event_type, ideology=c.ideology, severity=c.severity,
        date=item.published_at.date(), country=c.countries[0],
        place=c.places[0] if c.places else None, sk_link=c.sk_link, topic=c.domain, item_ids=[],
        event_keys=[], domains=[], has_tier_a=False, corroborated=False,
        first_seen=now, last_updated=now)


def _add(e: Event, item: Item, now: datetime) -> None:
    c = item.classification
    if item.id not in e.item_ids:
        e.item_ids.append(item.id)
    if item.url and item.url not in e.urls:
        e.urls.append(item.url)
    if c.event_key and c.event_key not in e.event_keys:
        e.event_keys.append(c.event_key)
    for d in [item.domain, *item.also_reported_by]:
        if d not in e.domains:
            e.domains.append(d)
    e.has_tier_a = e.has_tier_a or item.tier == "A"
    e.best_tier = _best(e.best_tier, item.tier)
    e.corroborated = e.has_tier_a or len(e.domains) >= 2
    e.severity = max(e.severity, c.severity)
    if c.domain == "terrorism":
        e.topic = "terrorism"
    if e.ideology == "unknown" and c.ideology != "unknown":
        e.ideology = c.ideology
    if SK_RANK[c.sk_link] > SK_RANK[e.sk_link]:
        e.sk_link = c.sk_link
    if e.place is None and c.places:
        e.place = c.places[0]
    if item.published_at.date() < e.date:
        e.date = item.published_at.date()
    e.last_updated = now


def refresh(events: list[Event], items: list[Item], now: datetime) -> list[Event]:
    """Stored events whose every report is in this run are rebuilt from the current labels,
    so a corrected classification also corrects the event (severity otherwise only rises).
    An event none of whose reports is still an incident is dropped."""
    present = {i.id: i for i in items}
    out = []
    for e in events:
        if not e.item_ids or not all(i in present for i in e.item_ids):
            out.append(e)
            continue
        members = sorted((present[i] for i in e.item_ids if eligible(present[i])),
                         key=lambda i: i.published_at)
        if not members:
            continue
        fresh = _new_event(members[0], now).model_copy(
            update={"id": e.id, "first_seen": e.first_seen})
        for m in members:
            _add(fresh, m, now)
        out.append(fresh)
    return out


def cluster(items: list[Item], events: list[Event], now: datetime) -> tuple[list[Event], list[str]]:
    """Assign items to events (setting item.event_id). Returns (all kept events, new ids)."""
    cutoff = (now - timedelta(days=KEEP_DAYS)).date()
    # Stored unrest events (made before unrest was left out) are dropped.
    events = refresh([e for e in events if e.date >= cutoff and e.topic != "unrest"], items, now)
    new_ids = []
    for item in sorted(filter(eligible, items), key=lambda i: i.published_at):
        event = next((e for e in events if item.id in e.item_ids), None) or \
            next((e for e in events if _matches(item, e)), None)
        if event is None:
            event = _new_event(item, now)
            events.append(event)
            new_ids.append(event.id)
        _add(event, item, now)
        item.event_id = event.id
    events, merged = merge_events(events, now)
    for item in items:
        if item.event_id in merged:
            item.event_id = merged[item.event_id]
    return events, [i for i in new_ids if i not in merged]
