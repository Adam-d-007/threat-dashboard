import json
from datetime import timedelta

import yaml

from monitor import settings
from monitor.ai.client import AiUnavailable
from monitor.briefing import brief, theatre_reports
from monitor.tests.helpers import NOW, FakeAi, label_dict, labelled
from pipeline.main import CONFIG

CFG = settings.load()["brief"]
CFG_SCORE = yaml.safe_load((CONFIG / "scoring.yaml").read_text())


def ua(title, **kw):
    return labelled(title, label_dict(countries=["UA", "RU"], summary_en=title), **kw)


def answer(*ids, upcoming=()):
    return json.dumps({
        "lines": [{"text_en": "Talks continued.", "text_sk": "Rokovania pokračovali.",
                   "item_ids": list(ids)}],
        "top_items": [{"item_id": i, "summary_en": "x", "summary_sk": "x"} for i in ids],
        "sk_angle_en": "Slovakia hosts refugees.", "sk_angle_sk": "Slovensko hostí utečencov.",
        "upcoming": [{"date": d, "title_en": t, "title_sk": t, "item_id": "1"}
                     for d, t in upcoming]})


def run(articles, ai, previous=None, write=True, now=NOW):
    return brief({a.id: a for a in articles}, previous, {}, ai, write, now, CFG, CFG_SCORE, CONFIG)


def theatre(geo, tid="russia_ukraine"):
    return next(t for t in geo.theatres if t.id == tid)


def test_a_theatre_gets_the_reports_that_name_its_countries_in_its_domains():
    mine = ua("Ukraine talks", hours_ago=2)
    official = ua("NATO statement on Ukraine", hours_ago=5, tier="A")
    old = ua("Old Ukraine news", hours_ago=30)
    elsewhere = labelled("Balkan talks", label_dict(countries=["RS"]))
    terror = labelled("Attack in Kyiv", label_dict(countries=["UA"], domain="terrorism"))
    none = labelled("Sport in Kyiv", label_dict(kind="none", countries=["UA"], summary_en="",
                                               summary_sk=""))
    articles = {a.id: a for a in (mine, official, old, elsewhere, terror, none)}
    got = theatre_reports(articles, ["UA", "RU"], CFG["theatres"]["russia_ukraine"], NOW, CFG)
    assert [a.title for a in got] == ["NATO statement on Ukraine", "Ukraine talks"]


def test_each_theatre_with_news_is_written_by_its_own_small_call():
    a, b = ua("Ukraine talks", hours_ago=1), ua("Russian strike", hours_ago=2)
    ai = FakeAi(answer("1", "2", "9", upcoming=[("2026-12-03", "Summit"), ("2026-11-01", "Past")]))
    geo, stats = run([a, b], ai)
    t = theatre(geo)
    assert stats == {"written": ["russia_ukraine"], "carried": [], "failed": {}, "stale": []}
    assert len(ai.asked) == 1 and len(geo.theatres) == 6
    # Short ids map back to the articles; a report that was not sent is not cited.
    assert t.lines[0].item_ids == [a.id, b.id] and t.lines[0].urls == [a.url, b.url]
    assert [x.item_id for x in t.top_items] == [a.id, b.id]
    assert t.written_at == NOW and t.written_by == "model of groq_120b"
    assert t.sk_angle_sk == "Slovensko hostí utečencov."
    news = [w for w in geo.watchlist if w.origin == "news"]
    assert [(w.title_en, w.verified, w.url) for w in news] == [("Summit", False, a.url)]
    assert theatre(geo, "middle_east").lines == []


def test_a_failed_call_keeps_the_old_text_with_its_real_date_and_says_it_is_stale():
    a = ua("Ukraine talks")
    geo, _ = run([a], FakeAi(answer("1", upcoming=[("2026-12-03", "Summit")])))
    later = NOW + timedelta(hours=9)
    geo2, stats = run([ua("More talks", hours_ago=-8)], FakeAi(AiUnavailable("down")), geo,
                      now=later)
    t = theatre(geo2)
    assert t.lines == theatre(geo).lines and t.written_at == NOW
    assert stats["failed"] == {"russia_ukraine": "down"} and stats["stale"] == ["russia_ukraine"]
    assert stats["carried"] == ["russia_ukraine"]
    # A date found in the news earlier stays on the watchlist.
    assert [w.title_en for w in geo2.watchlist if w.origin == "news"] == ["Summit"]


def test_text_older_than_three_days_is_dropped_not_shown():
    geo, _ = run([ua("Ukraine talks")], FakeAi(answer("1")))
    geo2, stats = run([], FakeAi(), geo, now=NOW + timedelta(hours=73))
    assert theatre(geo2).lines == [] and theatre(geo2).written_at is None
    assert stats["carried"] == [] and stats["stale"] == []


def test_outside_the_scoring_hours_no_model_is_asked_and_the_text_is_carried():
    a = ua("Ukraine talks")
    geo, _ = run([a], FakeAi(answer("1")))
    ai = FakeAi()
    geo2, stats = run([a], ai, geo, write=False, now=NOW + timedelta(hours=1))
    assert ai.asked == [] and theatre(geo2).lines == theatre(geo).lines
    assert stats["stale"] == []
