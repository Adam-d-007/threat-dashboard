"""Builders shared by the tests: articles, labels as a model would return them, and a model
that answers from a script."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from monitor.ai.labels import ArticleLabel
from monitor.models import Article
from pipeline.models import Item

NOW = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)


def item(title: str, snippet: str = "", hours_ago: float = 1, domain: str = "teraz.sk",
         lang: str = "sk", tier: str = "B", source_id: str = "tasr", also: tuple = ()) -> Item:
    url = f"https://{domain}/{hashlib.sha1(title.encode()).hexdigest()[:10]}"
    t = NOW - timedelta(hours=hours_ago)
    return Item(id=hashlib.sha1(url.encode()).hexdigest(), source_id=source_id, tier=tier,
                url=url, title=title, lang=lang, published_at=t, fetched_at=t, snippet=snippet,
                domain=domain, also_reported_by=list(also))


def article(title: str, **kw) -> Article:
    i = item(title, **kw)
    return Article(**i.model_dump(exclude={"published_estimated", "gdelt", "classification",
                                           "event_id"}), first_seen=i.published_at)


def label_dict(short: str = "1", **over) -> dict:
    """A label as a model returns it; by default commentary, the commonest kind."""
    base = {"id": short, "kind": "context", "domain": "geopolitics", "sk_link": "none",
            "countries": [], "incident_type": None, "severity": 0, "incident_date": None,
            "incident_country": None, "incident_place": None, "ideology": "unknown",
            "summary_en": "A summary.", "summary_sk": "Zhrnutie.", "confidence": 0.9}
    return base | over


def attack(short: str = "1", **over) -> dict:
    return label_dict(short, kind="new_incident", domain="terrorism", countries=["PL"],
                      incident_type="attack", severity=5, incident_date="2026-11-07",
                      incident_country="PL", incident_place="Kraków",
                      summary_en="A gunman opened fire on Kraków's main square, killing five.",
                      summary_sk="Strelec spustil paľbu na hlavnom námestí v Krakove.") | over


def labelled(title: str, lab: dict, model: str = "groq_120b", **kw) -> Article:
    """An article that already carries a label (stored with the article's own id)."""
    a = article(title, **kw)
    a.label = ArticleLabel.model_validate(lab | {"id": a.id})
    a.labelled_by, a.labelled_at = model, a.published_at
    return a


def batch(*labels: dict) -> str:
    return json.dumps({"items": list(labels)})


class _Models(dict):
    """Any model name maps to a model whose provider name is "model of <name>"."""

    def __missing__(self, name):
        return SimpleNamespace(model=f"model of {name}")


class FakeAi:
    """Gives the scripted answers in order: a text, a (text, model) pair, or an exception."""

    def __init__(self, *answers):
        self.answers, self.asked, self.t = list(answers), [], 0.0
        self.models = _Models()

    def clock(self) -> float:
        return self.t

    def ask(self, task, system, user, schema, name, parse, deadline=None):
        self.asked.append({"task": task, "user": user, "schema": schema})
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        text, model = answer if isinstance(answer, tuple) else (answer, "groq_120b")
        return parse(text), model

    def report(self) -> dict:
        return {}
