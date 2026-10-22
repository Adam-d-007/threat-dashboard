"""Stage 8, events: reports of the same incident become one event.

An item joins an event when they share an LLM event_key, or have the same event type and
country, places within 50 km and dates within one day. Events persist in events.json for 90
days, so a story covered over several days stays one event. An event is corroborated with two
or more independent domains, or one Tier A source. Unclassified items never enter."""

import hashlib
import math
from datetime import datetime, timedelta

from ..models import Event, Item, Place

DOMAINS = {"terrorism", "hybrid", "unrest"}
MAX_KM = 50
MAX_DAYS = 1
KEEP_DAYS = 90
SK_RANK = {"none": 0, "indirect": 1, "direct": 2}


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
    if abs((item.published_at.date() - e.date).days) > MAX_DAYS:
        return False
    place = c.places[0] if c.places else None
    return bool(place and e.place and km(place, e.place) <= MAX_KM)


def _new_event(item: Item, now: datetime) -> Event:
    c = item.classification
    return Event(
        id="evt_" + hashlib.sha1(item.id.encode()).hexdigest()[:12],
        title_en=c.summary_en or item.title, title_sk=c.summary_sk,
        event_type=c.event_type, ideology=c.ideology, severity=c.severity,
        date=item.published_at.date(), country=c.countries[0],
        place=c.places[0] if c.places else None, sk_link=c.sk_link, item_ids=[],
        event_keys=[], domains=[], has_tier_a=False, corroborated=False,
        first_seen=now, last_updated=now)


def _add(e: Event, item: Item, now: datetime) -> None:
    c = item.classification
    if item.id not in e.item_ids:
        e.item_ids.append(item.id)
    if c.event_key and c.event_key not in e.event_keys:
        e.event_keys.append(c.event_key)
    for d in [item.domain, *item.also_reported_by]:
        if d not in e.domains:
            e.domains.append(d)
    e.has_tier_a = e.has_tier_a or item.tier == "A"
    e.corroborated = e.has_tier_a or len(e.domains) >= 2
    e.severity = max(e.severity, c.severity)
    if e.ideology == "unknown" and c.ideology != "unknown":
        e.ideology = c.ideology
    if SK_RANK[c.sk_link] > SK_RANK[e.sk_link]:
        e.sk_link = c.sk_link
    if e.place is None and c.places:
        e.place = c.places[0]
    if item.published_at.date() < e.date:
        e.date = item.published_at.date()
    e.last_updated = now


def cluster(items: list[Item], events: list[Event], now: datetime) -> tuple[list[Event], list[str]]:
    """Assign items to events (setting item.event_id). Returns (all kept events, new ids)."""
    cutoff = (now - timedelta(days=KEEP_DAYS)).date()
    events = [e for e in events if e.date >= cutoff]
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
    return events, new_ids
