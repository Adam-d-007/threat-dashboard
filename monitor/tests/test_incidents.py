import json
from datetime import UTC, date, datetime, timedelta

from monitor.ai.client import AiUnavailable
from monitor.incidents import (
    REMOVED,
    apply_overrides,
    incident_id,
    match,
    needs_match,
    prune,
    seed,
    to_event,
)
from monitor.tests.helpers import NOW, FakeAi, attack, label_dict, labelled
from pipeline.models import Event
from pipeline.process.normalize import item_id

CFG = {"domains": ["terrorism", "hybrid"], "batch_size": 8, "max_seconds": 300,
       "candidate_days": 30, "max_candidates": 60, "max_attempts": 3}


def answer(**matches) -> str:
    return json.dumps({"matches": [{"id": k, "incident": v} for k, v in matches.items()]})


def update(**over) -> dict:
    return attack(kind="update", summary_en="The alleged Kraków shooter died in hospital.",
                  summary_sk="Údajný strelec z Krakova zomrel v nemocnici.") | over


def run(articles, incidents, *answers):
    ai = FakeAi(*answers)
    stats = match({a.id: a for a in articles}, incidents, ai, CFG, NOW)
    return stats, ai


def test_a_report_of_something_new_makes_an_incident_from_its_facts():
    a = labelled("Strelec v Krakove zabil päť ľudí", attack(), hours_ago=100, also=("sme.sk",))
    incidents = []
    stats, ai = run([a], incidents, (answer(r1="new"), "groq_120b"))
    (inc,) = incidents
    assert stats == {"attached": 0, "new": 1, "unanswered": 0, "stopped": None, "waiting": 0}
    assert inc.id == incident_id(a.id) and a.incident_id == inc.id and a.matched_by == "groq_120b"
    assert (inc.type, inc.severity, inc.country, inc.topic) == ("attack", 5, "PL", "terrorism")
    assert inc.date == date(2026, 11, 7)  # the day it happened, not the day of the article
    assert inc.title_en.startswith("A gunman opened fire") and len(inc.reports) == 1
    assert inc.domains == ["teraz.sk", "sme.sk"] and inc.corroborated
    # With no incident known, the only answer the schema allows is "new".
    enum = ai.asked[0]["schema"]["properties"]["matches"]["items"]["properties"]["incident"]["enum"]
    assert enum == ["new"]


def test_a_follow_up_joins_its_incident_and_is_not_listed_again():
    # The design's example: "The alleged Kraków shooter died in hospital" (2026-11-09).
    first = labelled("Strelec v Krakove zabil štyroch ľudí", attack(severity=4), hours_ago=120)
    later = labelled("Údajný strelec z Krakova zomrel v nemocnici", update(severity=5),
                     hours_ago=70, domain="bbc.co.uk", lang="en")
    incidents = []
    run([first], incidents, answer(r1="new"))
    stats, ai = run([first, later], incidents, answer(r1=incidents[0].id))
    (inc,) = incidents
    assert stats["attached"] == 1 and stats["new"] == 0
    assert [r.kind for r in inc.reports] == ["new_incident", "update"]
    assert inc.reports[1].summary_en == "The alleged Kraków shooter died in hospital."
    assert inc.severity == 5  # the toll rose
    assert inc.title_en.startswith("A gunman opened fire")  # the title stays the incident's
    assert inc.date == date(2026, 11, 7) and later.incident_id == inc.id
    # The model was offered the incident and only the report still waiting.
    sent = json.loads(ai.asked[0]["user"].split("\n", 1)[1].rsplit("\n", 1)[0])
    assert [i["id"] for i in sent["incidents"]] == [inc.id] and len(sent["reports"]) == 1


def test_two_reports_called_new_in_one_answer_are_not_two_incidents_yet():
    a = labelled("Bombové hrozby v talianskych školách", attack(
        incident_type="threat_statement", severity=1, incident_country="IT", incident_place=None,
        incident_date="2026-11-11"), hours_ago=30)
    b = labelled("Bomb hoaxes close hundreds of Italian schools", attack(
        incident_type="threat_statement", severity=1, incident_country="IT", incident_place=None,
        incident_date="2026-11-11"), hours_ago=29, domain="bbc.co.uk", lang="en")
    incidents = []
    first_id = incident_id(a.id)
    stats, ai = run([a, b], incidents, answer(r1="new", r2="new"), answer(r1=first_id))
    assert len(incidents) == 1 and stats["new"] == 1 and stats["attached"] == 1
    assert len(incidents[0].reports) == 2 and b.incident_id == first_id
    # The second question offered the incident the first answer had just made.
    second = ai.asked[1]["schema"]["properties"]["matches"]["items"]["properties"]["incident"]
    assert second["enum"] == [first_id, "new"]


def test_an_update_to_an_incident_never_reported_makes_that_incident_dated_when_it_happened():
    a = labelled("Údajný strelec z Krakova zomrel v nemocnici", update(), hours_ago=70)
    incidents = []
    run([a], incidents, answer(r1="new"))
    assert incidents[0].date == date(2026, 11, 7) and incidents[0].type == "attack"
    assert incidents[0].reports[0].kind == "update"


def test_a_date_after_the_report_is_not_believed():
    a = labelled("Útok", attack(incident_date="2026-12-24"), hours_ago=10)
    incidents = []
    run([a], incidents, answer(r1="new"))
    assert incidents[0].date == a.published_at.date()


def test_commentary_other_topics_and_reports_without_a_country_are_never_matched():
    quiet = [
        labelled("Komentár", label_dict()),
        labelled("Výtržnosti", attack(domain="unrest")),
        labelled("Kybernetický útok", attack(domain="cyber")),
        labelled("Útok kdesi", attack(incident_country=None, incident_place=None)),
    ]
    assert not any(needs_match(a, CFG) for a in quiet)
    stats, ai = run(quiet, [])
    assert ai.asked == [] and stats["waiting"] == 0


def test_when_no_model_answers_reports_wait_and_nothing_is_listed():
    a = labelled("Útok v Krakove", attack())
    incidents = []
    stats, _ = run([a], incidents, AiUnavailable("groq_120b: HTTP 503"))
    assert incidents == [] and a.incident_id is None
    assert stats["stopped"] == "groq_120b: HTTP 503" and stats["waiting"] == 1


def test_a_report_the_answers_keep_skipping_is_left_alone_after_three_tries():
    a = labelled("Útok A", attack(), hours_ago=3)
    b = labelled("Útok B", attack(incident_place="Varšava"), hours_ago=2)
    for attempt in (1, 2, 3):
        b.incident_id = None
        run([a, b], [], answer(r2="new"))  # r1, the older report, is never answered
        assert a.match_attempts == attempt and a.incident_id is None
    assert not needs_match(a, CFG)
    _, ai = run([a], [])
    assert ai.asked == []


def test_one_tier_a_source_or_two_outlets_corroborate():
    alone = labelled("Útok A", attack(), tier="B")
    official = labelled("Útok B", attack(incident_place="Lublin"), tier="A", source_id="minv")
    incidents = []
    run([alone], incidents, answer(r1="new"))
    run([official], incidents, answer(r1="new"))
    assert [i.corroborated for i in incidents] == [False, True]
    assert incidents[1].has_tier_a and incidents[1].best_tier == "A"


def v1_event(eid, severity, **over) -> Event:
    base = dict(
        id=eid, title_en="A gunman opened fire in Kraków.", title_sk="Streľba v Krakove.",
        event_type="attack", ideology="unknown", severity=severity, date=date(2026, 11, 7),
        country="PL", sk_link="indirect", topic="terrorism", item_ids=["x"],
        urls=["https://teraz.sk/a", "https://bbc.co.uk/b"], domains=["teraz.sk", "bbc.co.uk"],
        has_tier_a=False, best_tier="B", corroborated=True,
        first_seen=datetime(2026, 11, 7, 13, tzinfo=UTC),
        last_updated=datetime(2026, 11, 9, 4, tzinfo=UTC))
    return Event(**base | over)


def test_the_old_events_carry_over_as_incidents_that_score_the_same():
    events = [v1_event("evt_aaa", 5), v1_event("evt_bbb", 0, event_type="other"),
              v1_event("evt_ccc", 1, event_type="arrest", urls=[], domains=["sme.sk"],
                       corroborated=False, has_tier_a=False, best_tier="C", topic="hybrid"),
              v1_event("evt_ddd", 3), v1_event("evt_old", 4, date=date(2026, 7, 1))]
    incidents = seed(events, ["inc_ddd"], NOW, 90, item_id)
    assert [i.id for i in incidents] == ["inc_aaa", "inc_ccc"]  # no severity 0, removed or old
    for inc, old in zip(incidents, (events[0], events[2]), strict=True):
        new = to_event(inc)
        for f in ("severity", "date", "country", "event_type", "sk_link", "topic",
                  "corroborated", "has_tier_a", "best_tier", "title_en", "ideology"):
            assert getattr(new, f) == getattr(old, f), f
        assert inc.seeded_from == old.id
    assert [r.url for r in incidents[0].reports] == ["https://teraz.sk/a", "https://bbc.co.uk/b"]
    assert incidents[0].reports[0].article_id == item_id("https://teraz.sk/a")


def test_corrections_by_hand_merge_remove_and_detach_and_can_be_applied_again():
    a = labelled("Útok A", attack(), hours_ago=30)
    b = labelled("Útok A znova", attack(), hours_ago=29, domain="sme.sk")
    c = labelled("Recenzia filmu o útoku", attack(incident_place="Lublin"), hours_ago=28)
    d = labelled("Druhý útok", update(), hours_ago=27, domain="bbc.co.uk")
    articles = {x.id: x for x in (a, b, c, d)}
    incidents = []
    for x in (a, b, c):
        match({x.id: x}, incidents, FakeAi(answer(r1="new")), CFG, NOW)
    match({d.id: d}, incidents, FakeAi(answer(r1=incidents[0].id)), CFG, NOW)
    ia, ib, ic = (i.id for i in incidents)
    overrides = {"merge": [{"into": ia, "from": ib, "note": "same attack"}],
                 "remove": [{"id": ic, "note": "a film review"}],
                 "detach": [{"url": d.url, "note": "a second attack"}]}
    removed = []
    for _ in (1, 2):
        done = apply_overrides(incidents, articles, overrides, removed, NOW)
        assert [(c_.action, c_.applied) for c_ in done] == [
            ("merge", True), ("remove", True), ("detach", True)]
        assert [i.id for i in incidents] == [ia, incident_id(d.id)]
        assert [r.article_id for r in incidents[0].reports] == [a.id, b.id]
        assert incidents[0].corroborated and incidents[1].reports[0].kind == "new_incident"
        assert b.incident_id == ia and c.incident_id == REMOVED and removed == [ic]
        assert d.incident_id == incident_id(d.id)
    assert not needs_match(c, CFG)  # a removed incident's report is not matched again


def test_a_correction_naming_an_incident_that_does_not_exist_says_so():
    done = apply_overrides([], {}, {"merge": [{"into": "inc_x", "from": "inc_y", "note": "n"}],
                                    "detach": [{"url": "https://x", "note": "n"}]}, [], NOW)
    assert [c.applied for c in done] == [False, False]


def test_incidents_older_than_the_scoring_needs_are_dropped():
    a = labelled("Útok", attack(incident_date="2026-08-01"), hours_ago=1)
    b = labelled("Útok dnes", attack(incident_place="Lublin", incident_date="2026-11-12"))
    incidents = []
    run([a], incidents, answer(r1="new"))
    run([b], incidents, answer(r1="new"))
    assert [i.date for i in prune(incidents, NOW + timedelta(days=1), 90)] == [date(2026, 11, 12)]


def test_the_incident_is_dated_the_day_most_of_its_reports_give():
    first = labelled("Strelec v Krakove", attack(incident_date="2026-11-06"), hours_ago=120)
    others = [labelled(f"Krakov {n}", update(incident_date="2026-11-07"), hours_ago=100 - n)
              for n in (1, 2)]
    incidents = []
    run([first], incidents, answer(r1="new"))
    assert incidents[0].date == date(2026, 11, 6)
    run(others[:1], incidents, answer(r1=incidents[0].id))
    assert incidents[0].date == date(2026, 11, 6)  # one against one: the first report's day
    run(others[1:], incidents, answer(r1=incidents[0].id))
    assert incidents[0].date == date(2026, 11, 7)
