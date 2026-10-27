"""Stage 6, classification: the LLM labels items in batches; keyword rules label whatever the
LLM could not. Results are cached by item id so an item is sent to the LLM only once."""

import hashlib
import json
import logging

from pydantic import ValidationError

from ..llm.client import LlmBadOutput, LlmClient, LlmUnavailable, ask
from ..llm.prompts import CLASSIFY_SYSTEM, classify_user
from ..llm.schemas import Batch, ItemLabel
from ..models import Classification, Item
from .prefilter import compile_terms, fold

# Cached labels are reused only if they came from the same instructions: a prompt change
# relabels items still in the window (their events are rebuilt in cluster.refresh).
PROMPT_ID = hashlib.sha1(CLASSIFY_SYSTEM.encode()).hexdigest()[:12]

log = logging.getLogger("pipeline.classify")

# Keyword rules, matched on folded text (lowercase, no diacritics) at word starts; a term
# ending in ! must match a whole word ("war!" must not match "Warsaw").
_RULES = {
    "terror": ["terror", "terori", "dzihad", "jihad", "djihad", "dschihad", "islamic state",
               "islamsk", "isis!", "daesh", "extremis", "ekstremis", "szelsoseg"],
    "attack": ["attack", "utok", "anschlag", "attentat", "attaque", "zamach", "merenylet",
               "explos", "vybuch", "wybuch", "robban", "bomb", "shooting", "strelb", "fusillade",
               "schusse", "stabbing", "messerangriff", "nozom", "nozem", "kesel"],
    "arrest": ["arrest", "zadrz", "zatrzym", "festgenommen", "festnahme", "interpelle",
               "letartoztat", "orizetbe", "aresztowa"],
    "plot": ["plot!", "plots!", "foiled", "priprav", "planovan", "vereitelt"],
    "hybrid": ["sabotage", "sabotaz", "szabotazs", "drone", "dron", "airspace", "vzdusn",
               "luftraum", "disinformation", "dezinform", "desinformation", "hybrid"],
    "cyber": ["cyberattack", "cyber attack", "kyberneticke", "cyberangriff", "cyberatak",
              "kibertamad", "ransomware", "hacker", "haker"],
    "geo": ["war!", "vojn", "valk", "krieg", "guerre", "wojn", "haboru", "nato!", "sanction",
            "sankci", "missile", "raket", "ceasefire", "primeri", "invasion"],
    "slovak": ["sloven", "slovak", "slowak", "slowac", "szlovak", "bratislav", "kosic",
               "pozsony"],
}
_RX = {k: compile_terms({k: v}) for k, v in _RULES.items()}


def rules_label(item: Item) -> Classification:
    text = fold(f"{item.title} {item.snippet}")
    hit = {k: bool(rx.search(text)) for k, rx in _RX.items()}
    if hit["terror"]:
        domain = "terrorism"
    elif hit["cyber"]:
        domain = "cyber"
    elif hit["hybrid"]:
        domain = "hybrid"
    elif hit["geo"]:
        domain = "geopolitics"
    else:
        domain = "other"
    terror = domain == "terrorism"
    if terror and hit["arrest"]:
        event_type, severity = ("plot_disrupted" if hit["plot"] else "arrest"), 1
    elif terror and hit["attack"]:
        event_type, severity = "attack", 3
    elif domain == "hybrid" and "sabot" in text:
        event_type, severity = "sabotage", 0
    else:
        event_type, severity = "other", 0
    return Classification(
        status="rules", relevant=domain != "other", domain=domain, event_type=event_type,
        ideology="unknown", severity=severity,
        sk_link="direct" if hit["slovak"] else "none",
        countries=["SK"] if hit["slovak"] else [], confidence=0.3)


# Languages spoken in one country, and words that name it (folded: no diacritics, lowercase).
HOME = {"sk": ("SK", ("sloven", "slovak", "bratislav")), "cs": ("CZ", ("cesk", "czech", "praha")),
        "hu": ("HU", ("magyar", "hungar", "budapest")), "pl": ("PL", ("pols", "poland", "warsz"))}


def assumed_home_country(item: Item, c: Classification, place_refs: list) -> bool:
    """A severe incident placed in the source's own country although the item names no place
    and never mentions that country: the model assumed it. On 2026-10-23 a TASR headline about
    a church shooting in Jordan, with no place in it, became seven deaths in Slovakia, with the
    place "Slovakia" made up. So a place counts only if the item's text names it (by the start
    of the name, since Slovak inflects: "Bratislava" appears as "v Bratislave")."""
    home = HOME.get(item.lang)
    if not home or c.severity < 3 or c.countries != [home[0]]:
        return False
    text = fold(f"{item.title} {item.snippet}")
    named = [r for r in place_refs
             if (n := fold(r.get("name") or "")) and n[:max(4, len(n) - 2)] in text]
    return not named and not any(word in text for word in home[1])


def _from_label(label: ItemLabel) -> Classification:
    # Places are geocoded later; until then the names wait in place_refs.
    return Classification(
        status="llm", relevant=label.relevant, domain=label.domain, event_type=label.event_type,
        ideology=label.ideology, severity=label.severity, sk_link=label.sk_link,
        countries=label.countries, event_key=label.event_key, summary_en=label.summary_en,
        summary_sk=label.summary_sk, confidence=label.confidence)


def _labels(text: str, ids: set[str]) -> dict[str, ItemLabel]:
    """Valid labels by item id. A malformed label is dropped, so its item counts as left out
    and is asked again; only an answer with no valid label at all is rejected."""
    raw = Batch.model_validate(json.loads(text)).items
    labels, errors = {}, []
    for r in raw:
        try:
            lab = ItemLabel.model_validate(r)
        except ValidationError as e:
            errors.append(e)
            continue
        if lab.id in ids:
            labels[lab.id] = lab
    if errors and not labels:
        raise errors[0]
    if errors:
        log.warning("%d labels malformed, their items are asked again: %s", len(errors),
                    str(errors[0])[:200])
    return labels


def _ask(client: LlmClient, batch: list[Item]) -> dict[str, ItemLabel]:
    """One batch, validated (see llm.client.ask for the retries). Raises when all fail."""
    ids = {i.id for i in batch}
    return ask(client, CLASSIFY_SYSTEM, classify_user(batch), lambda t: _labels(t, ids))


def classify(items: list[Item], client: LlmClient | None, cfg: dict,
             cache: dict[str, dict]) -> tuple[dict[str, list[dict]], dict]:
    """Label every item in place. Returns (place refs by item id, stats). cache maps item id
    to {"classification": ..., "places": [...]} from earlier runs and is updated."""
    places: dict[str, list[dict]] = {}
    todo = []
    for item in items:
        hit = cache.get(item.id)
        if hit and hit.get("prompt") == PROMPT_ID:
            item.classification = Classification.model_validate(hit["classification"])
            places[item.id] = hit["places"]
        else:
            todo.append(item)
    stats = {"cached": len(items) - len(todo), "llm": 0, "rules": 0, "batches_failed": 0}
    size, budget = cfg["batch_size"], cfg["budget"]["classify"]
    if client is not None:
        # Labelling may use only its share of the AI time; the rest is kept for the regional
        # assessments and the brief (on 2026-10-25 labelling 149 items used it all up).
        client.deadline = client.started + cfg.get("max_seconds", 480) * cfg.get(
            "classify_share", 1.0)
    pending, unlabelled = todo, []
    for attempt in (1, 2):
        skipped = []
        for start in range(0, len(pending), size):
            batch = pending[start:start + size]
            labels: dict[str, ItemLabel] = {}
            if client and client.available and client.calls < budget:
                try:
                    labels = _ask(client, batch)
                except LlmUnavailable:
                    log.warning("no LLM available; rules for the remaining items")
                except (json.JSONDecodeError, ValidationError, LlmBadOutput) as e:
                    stats["batches_failed"] += 1
                    log.warning("batch failed, rules instead: %s", str(e)[:200])
            for item in batch:
                label = labels.get(item.id)
                if label:
                    item.classification = _from_label(label)
                    places[item.id] = [p.model_dump() for p in label.places]
                    cache[item.id] = {"classification": item.classification.model_dump(
                        mode="json"), "places": places[item.id],
                        "at": item.published_at.isoformat(), "prompt": PROMPT_ID}
                    stats["llm"] += 1
                elif labels and attempt == 1:
                    skipped.append(item)  # the model answered the batch but left this one out
                else:
                    unlabelled.append(item)
        if not skipped:
            break
        log.info("%d items were left out of the model's answers; asking once more",
                 len(skipped))
        pending = skipped
    if client is not None:
        client.deadline = None
    for item in unlabelled:
        item.classification = rules_label(item)
        places[item.id] = []
        stats["rules"] += 1
    for item in items:
        c = item.classification
        if c and c.status == "llm" and assumed_home_country(item, c, places.get(item.id, [])):
            # Its summary repeats the made-up place, so the report is set aside entirely; the
            # same story arrives correctly placed from other outlets.
            log.info("%s: no place and no mention of %s; report set aside", item.id, c.countries)
            item.classification = c.model_copy(update={
                "countries": [], "relevant": False, "summary_en": None, "summary_sk": None})
    log.info("classified: %s", stats)
    return places, stats
