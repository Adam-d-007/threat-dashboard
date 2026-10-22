"""Exact deduplication on the canonical URL. Near-duplicate titles come in Phase 3."""

from ..models import Item


def dedupe(items: list[Item]) -> list[Item]:
    """Keep the earliest item per id."""
    by_id: dict[str, Item] = {}
    for item in sorted(items, key=lambda i: i.published_at):
        by_id.setdefault(item.id, item)
    return list(by_id.values())
