import json
from datetime import timedelta

import pytest

from monitor import store
from monitor.ai.client import AiUnavailable
from monitor.ingest import ingest, prune
from monitor.labelling import label, waiting
from monitor.tests.helpers import NOW, FakeAi, article, attack, batch, item, label_dict, labelled

PRE = {"keep_groups": ["official"], "max_items": 600,
       "terms": {"en": ["attack", "terror"], "sk": ["utok", "strelb"]}}
GROUPS = {"tasr": "slovak_press", "minv": "official"}
CFG = {"batch_size": 2, "max_seconds": 420, "max_age_hours": 36, "max_attempts": 3}


def test_only_items_worth_a_models_time_become_articles():
    articles = {}
    items = [item("Útok v Krakove"), item("Počasie na víkend"),
             item("Minister otvoril cestu", source_id="minv"),
             item("Starý útok", hours_ago=40)]
    assert ingest(articles, items, GROUPS, PRE, NOW, NOW - timedelta(hours=36)) == 2
    assert sorted(a.title for a in articles.values()) == ["Minister otvoril cestu",
                                                           "Útok v Krakove"]
    assert all(a.label is None and a.first_seen == NOW for a in articles.values())


def test_a_known_article_is_not_added_twice_but_learns_who_else_reported_it():
    articles = {}
    ingest(articles, [item("Útok v Krakove")], GROUPS, PRE, NOW, NOW - timedelta(hours=36))
    again = item("Útok v Krakove", also=("sme.sk", "bbc.co.uk"))
    assert ingest(articles, [again], GROUPS, PRE, NOW + timedelta(hours=1), NOW - timedelta(hours=36)) == 0
    (a,) = articles.values()
    assert a.also_reported_by == ["bbc.co.uk", "sme.sk"] and a.first_seen == NOW


def test_unused_articles_leave_after_two_days_and_the_rest_after_a_week():
    none = labelled("Šport", label_dict(kind="none", domain="other", summary_en="",
                                        summary_sk=""), hours_ago=50)
    lost = article("Útok bez odpovede", hours_ago=50)
    lost.given_up = "not labelled within 36 hours"
    kept = labelled("Útok v Krakove", attack(), hours_ago=50)
    old = labelled("Útok spred týždňa", attack(), hours_ago=24 * 8)
    articles = {a.id: a for a in (none, lost, kept, old)}
    prune(articles, NOW)
    assert list(articles) == [kept.id]


def test_a_batch_is_labelled_and_each_article_records_the_model():
    a, b = article("Strelec v Krakove zabil päť ľudí", hours_ago=2), article("Komentár", hours_ago=3)
    articles = {x.id: x for x in (a, b)}
    ai = FakeAi((batch(attack("1"), label_dict("2")), "gemini_36"))
    stats = label(articles, ai, CFG, NOW)
    assert stats == {"labelled": 2, "left_out": 0, "given_up": 0, "stopped": None, "waiting": 0}
    assert a.label.kind == "new_incident" and a.label.id == a.id
    assert a.labelled_by == "gemini_36" and a.labelled_at == NOW
    assert a.place.name == "Kraków" and a.place.precision == "city"
    assert b.label.kind == "context" and b.place is None
    # The model saw short ids and the article's own text, newest first.
    rows = json.loads(ai.asked[0]["user"].split("\n", 1)[1].rsplit("\n", 1)[0])
    assert [r["id"] for r in rows] == ["1", "2"] and rows[0]["title"] == a.title


def test_an_article_the_answer_left_out_waits_and_is_given_up_after_three_tries():
    b = article("Útok B", hours_ago=5)
    articles = {b.id: b}
    for attempt in (1, 2, 3):
        # Each hour a newer article shares the batch; the answer only ever labels that one.
        newer = article(f"Útok {attempt}", hours_ago=4 - attempt)
        articles[newer.id] = newer
        stats = label(articles, FakeAi(batch(attack("1"))), CFG, NOW)
        assert newer.label is not None
        assert b.label is None and b.label_attempts == attempt
    assert b.given_up == "left out or mislabelled 3 times" and stats["given_up"] == 1
    assert waiting(articles) == []


def test_a_label_that_contradicts_itself_is_not_used():
    a, b = article("Útok A", hours_ago=1), article("Komentár B", hours_ago=2)
    articles = {x.id: x for x in (a, b)}
    stats = label(articles, FakeAi(batch(attack("1"), label_dict("2", severity=4))), CFG, NOW)
    assert stats["labelled"] == 1 and stats["left_out"] == 1
    assert b.label is None and b.label_attempts == 1


def test_when_no_model_answers_the_articles_wait_and_nothing_is_guessed():
    a = article("Teroristický útok v Bratislave", hours_ago=1)
    articles = {a.id: a}
    stats = label(articles, FakeAi(AiUnavailable("groq_120b: HTTP 503")), CFG, NOW)
    assert stats["stopped"] == "groq_120b: HTTP 503" and stats["waiting"] == 1
    assert a.label is None and a.label_attempts == 0 and a.given_up is None


def test_an_article_nobody_labelled_in_time_is_given_up_and_counted():
    a = article("Útok", hours_ago=37)
    articles = {a.id: a}
    ai = FakeAi()
    stats = label(articles, ai, CFG, NOW)
    assert a.given_up == "not labelled within 36 hours" and stats["given_up"] == 1
    assert ai.asked == []


def test_a_severe_incident_placed_in_the_sources_own_country_without_saying_so_loses_its_place():
    a = article("Streľba v kostole: sedem mŕtvych", snippet="Útočník spustil paľbu počas omše.")
    b = article("Streľba v Bratislave: dvaja mŕtvi", snippet="Polícia zasahuje v centre mesta.",
                hours_ago=2)
    articles = {x.id: x for x in (a, b)}
    made_up = attack("1", incident_country="SK", incident_place="Slovakia", countries=["SK"])
    real = attack("2", incident_country="SK", incident_place="Bratislava", countries=["SK"])
    label(articles, FakeAi(batch(made_up, real)), CFG, NOW)
    assert a.label.kind == "new_incident"
    assert a.label.incident_country is None and a.label.incident_place is None and a.place is None
    assert b.label.incident_country == "SK" and b.place.name == "Bratislava"


def test_articles_survive_a_round_trip_through_the_state_folder(tmp_path):
    a = labelled("Útok v Krakove", attack())
    store.save_articles(tmp_path, {a.id: a}, NOW)
    assert store.load_articles(tmp_path) == {a.id: a}
    assert (tmp_path / "v2" / "state" / "articles.json").exists()


def test_a_broken_state_file_stops_the_run(tmp_path):
    path = tmp_path / "v2" / "state" / "articles.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"articles": [{"id": "x"}]}')
    with pytest.raises(ValueError):
        store.load_articles(tmp_path)


def test_one_failed_batch_does_not_end_the_hour_while_a_model_is_still_in_use():
    a, b, c = (article(f"Útok {n}", hours_ago=n) for n in (1, 2, 3))
    articles = {x.id: x for x in (a, b, c)}
    ai = FakeAi(AiUnavailable("groq_120b: HTTP 400; gemini_36: HTTP 503"), batch(attack("1")))
    ai.in_use = ["groq_120b"]
    stats = label(articles, ai, CFG, NOW)
    assert a.label is None and b.label is None and c.label is not None
    assert stats["labelled"] == 1 and stats["waiting"] == 2
    assert a.label_attempts == 0  # nobody answered: not the article's fault


def test_unlabelled_articles_from_before_the_window_are_dropped_and_not_taken_in_again():
    old, fresh = article("Starý útok", hours_ago=30), article("Nový útok", hours_ago=2)
    done = labelled("Útok v Krakove", attack(), hours_ago=30)
    articles = {a.id: a for a in (old, fresh, done)}
    again = item("Starý útok", hours_ago=30)
    assert ingest(articles, [again], GROUPS, PRE, NOW, NOW - timedelta(hours=6)) == 0
    assert sorted(a.title for a in articles.values()) == ["Nový útok", "Útok v Krakove"]
