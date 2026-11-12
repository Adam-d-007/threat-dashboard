"""Stage 2, labelling: waiting articles go to a model, a batch at a time, newest first.

There is no keyword fallback. An article no model could label stays waiting for the next
hourly run; after max_age_hours it is given up and counted, never guessed.
"""

import logging
from datetime import datetime, timedelta

from pipeline.process.geocode import geocode
from pipeline.process.prefilter import fold

from .ai.client import AiUnavailable
from .ai.labels import (
    BATCH_SCHEMA,
    INCIDENT_KINDS,
    LABEL_SYSTEM,
    ArticleLabel,
    label_user,
    parse_labels,
)
from .models import Article

log = logging.getLogger("monitor.label")

# Languages spoken in one country, and words that name it (folded: no diacritics, lowercase).
HOME = {"sk": ("SK", ("sloven", "slovak", "bratislav")), "cs": ("CZ", ("cesk", "czech", "praha")),
        "hu": ("HU", ("magyar", "hungar", "budapest")), "pl": ("PL", ("pols", "poland", "warsz"))}
SEVERE = 3


def assumed_home_country(a: Article, lab: ArticleLabel) -> bool:
    """A severe incident placed in the source's own country although the article names no
    place and never mentions that country: the model assumed it. On 2026-10-23 a TASR headline
    about a church shooting in Jordan, with no place in it, became seven deaths in Slovakia.
    A place counts only if the text names it (by the start of the name, since Slovak inflects:
    "Bratislava" appears as "v Bratislave")."""
    home = HOME.get(a.lang)
    if not home or lab.severity < SEVERE or lab.incident_country != home[0]:
        return False
    text = fold(f"{a.title} {a.snippet}")
    place = fold(lab.incident_place or "")
    named = bool(place) and place[:max(4, len(place) - 2)] in text
    return not named and not any(word in text for word in home[1])


def waiting(articles: dict[str, Article]) -> list[Article]:
    """Articles no model has labelled yet, newest first."""
    return sorted((a for a in articles.values() if a.label is None and not a.given_up),
                  key=lambda a: a.published_at, reverse=True)


def rows_of(batch: list[Article]) -> list[dict]:
    return [{"id": str(n), "source": a.domain, "lang": a.lang,
             "published": a.published_at.isoformat(), "title": a.title, "snippet": a.snippet}
            for n, a in enumerate(batch, 1)]


def _parse(text: str, ids: set[str]) -> dict[str, ArticleLabel]:
    """Labels that are valid and do not contradict themselves. An answer with none is refused,
    so the next model is asked."""
    labels, errors = parse_labels(text, ids)
    good = {i: lab for i, lab in labels.items() if not lab.problems()}
    bad = errors + [f"{i}: {'; '.join(lab.problems())}" for i, lab in labels.items()
                    if lab.problems()]
    if bad:
        log.warning("%d labels unusable, first: %s", len(bad), bad[0])
    if not good:
        raise ValueError(f"no usable label in the answer: {bad[:1]}")
    return good


def apply(a: Article, lab: ArticleLabel, model: str, now: datetime) -> None:
    if lab.kind in INCIDENT_KINDS and assumed_home_country(a, lab):
        # The report stays; only the made-up place goes, so it cannot become an incident.
        log.info("%s: no place and no mention of %s; place set aside", a.id, lab.incident_country)
        lab = lab.model_copy(update={"incident_country": None, "incident_place": None})
    a.label = lab.model_copy(update={"id": a.id})
    a.labelled_by, a.labelled_at = model, now
    if lab.incident_place and lab.incident_country:
        places = geocode([{"name": lab.incident_place, "country": lab.incident_country}])
        a.place = places[0] if places else None


def label(articles: dict[str, Article], ai, cfg: dict, now: datetime) -> dict:
    """Label what is waiting within the stage's time. Returns counts and, when it stopped
    early, why."""
    limit = now - timedelta(hours=cfg["max_age_hours"])
    stats = {"labelled": 0, "left_out": 0, "given_up": 0, "stopped": None}
    for a in waiting(articles):
        if a.published_at < limit:
            a.given_up = f"not labelled within {cfg['max_age_hours']} hours"
            stats["given_up"] += 1
    queue = waiting(articles)
    deadline = ai.clock() + cfg["max_seconds"]
    for start in range(0, len(queue), cfg["batch_size"]):
        batch = queue[start:start + cfg["batch_size"]]
        by_short = {str(n): a for n, a in enumerate(batch, 1)}
        try:
            labels, model = ai.ask("label", LABEL_SYSTEM, label_user(rows_of(batch)),
                                   BATCH_SCHEMA, "labels",
                                   lambda t, ids=set(by_short): _parse(t, ids), deadline)
        except AiUnavailable as e:
            stats["stopped"] = str(e)
            log.warning("labelling stopped: %s", e)
            break
        for short, a in by_short.items():
            if short in labels:
                apply(a, labels[short], model, now)
                stats["labelled"] += 1
                continue
            a.label_attempts += 1
            stats["left_out"] += 1
            if a.label_attempts >= cfg["max_attempts"]:
                a.given_up = f"left out or mislabelled {a.label_attempts} times"
                stats["given_up"] += 1
    stats["waiting"] = len(waiting(articles))
    log.info("labelling: %s", stats)
    return stats
