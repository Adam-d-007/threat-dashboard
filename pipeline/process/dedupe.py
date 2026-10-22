"""Stage 4, deduplication: exact (same canonical URL) and near duplicates (the same story in
several outlets). The earliest item is kept and the other outlets go into also_reported_by,
because they count toward corroboration."""

import re
from datetime import timedelta

from rapidfuzz import fuzz

from ..models import Item
from .prefilter import fold

NEAR_WINDOW = timedelta(hours=48)
NEAR_SCORE = 90
# token_set_ratio scores 100 whenever one title's words are a subset of the other's, so a
# short title ("Attack in Vienna") would swallow longer stories. Both titles need this many.
MIN_WORDS = 5


def _key(title: str) -> str:
    return re.sub(r"[^\w ]", " ", fold(title))


def _absorb(kept: Item, dup: Item) -> None:
    for d in [dup.domain, *dup.also_reported_by]:
        if d != kept.domain and d not in kept.also_reported_by:
            kept.also_reported_by.append(d)


def dedupe(items: list[Item]) -> list[Item]:
    """Keep the earliest item per URL, then fold near-duplicate titles into the earliest."""
    by_id: dict[str, Item] = {}
    for item in sorted(items, key=lambda i: i.published_at):
        if item.id in by_id:
            _absorb(by_id[item.id], item)
        else:
            by_id[item.id] = item
    kept: list[tuple[str, Item]] = []
    for item in by_id.values():  # still in published order
        key = _key(item.title)
        original = None
        if len(key.split()) >= MIN_WORDS:
            original = next((other for k, other in kept
                             if other.lang == item.lang
                             and item.published_at - other.published_at <= NEAR_WINDOW
                             and len(k.split()) >= MIN_WORDS
                             and fuzz.token_set_ratio(k, key) >= NEAR_SCORE), None)
        if original:
            _absorb(original, item)
        else:
            kept.append((key, item))
    return [item for _, item in kept]
