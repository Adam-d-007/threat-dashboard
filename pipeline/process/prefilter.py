"""Stage 5, prefilter without an LLM: keep items from official and backbone sources, and items
whose title or snippet contains a security term in any of the eight languages. At most
max_items survive, by tier and then recency."""

import re
import unicodedata

from ..models import Item

TIER_ORDER = {"A": 0, "B": 1, "C": 2}


def fold(text: str) -> str:
    """Lowercase without diacritics: 'Výbuchu' -> 'vybuchu'."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def compile_terms(terms: dict[str, list[str]]) -> re.Pattern:
    """One pattern matching any term at the start of a word, in any language. A term ending
    in ! must match a whole word."""
    parts = []
    for t in sorted({fold(t) for lang in terms.values() for t in lang}, key=len, reverse=True):
        parts.append(re.escape(t[:-1]) + r"(?!\w)" if t.endswith("!") else re.escape(t))
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + ")")


def matches(item: Item, pattern: re.Pattern) -> bool:
    return bool(pattern.search(fold(f"{item.title} {item.snippet}")))


def prefilter(items: list[Item], groups: dict[str, str], cfg: dict) -> list[Item]:
    """groups maps source_id to its group."""
    pattern = compile_terms(cfg["terms"])
    keep = set(cfg["keep_groups"])
    kept = [i for i in items if groups.get(i.source_id) in keep or matches(i, pattern)]
    kept.sort(key=lambda i: (TIER_ORDER[i.tier], -i.published_at.timestamp()))
    return kept[: cfg["max_items"]]
