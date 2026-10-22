"""Phase 4 acceptance: gates, disagreement, hysteresis, smoothing, incident replays."""

from datetime import UTC, datetime, timedelta

import pytest
import yaml

from pipeline.main import CONFIG
from pipeline.models import AnchorReading, Event
from pipeline.score import gates
from pipeline.score.components import curve
from pipeline.score.terrorism import disagree, score_region

CFG = yaml.safe_load((CONFIG / "scoring.yaml").read_text())
NOW = datetime(2026, 10, 22, 13, 5, tzinfo=UTC)


def ev(country, etype="attack", sev=3, days_ago=1, corroborated=True, sk="none", tier_a=False,
       now=NOW, eid=None):
    d = (now - timedelta(days=days_ago)).date()
    return Event(id=eid or f"evt_{country}_{etype}_{sev}_{days_ago}_{sk}_{tier_a}",
                 title_en=f"{etype} in {country}", event_type=etype, ideology="unknown",
                 severity=sev, date=d, country=country, sk_link=sk, item_ids=["i"],
                 domains=["a.sk", "b.sk"] if corroborated else ["a.sk"], has_tier_a=tier_a,
                 best_tier="A" if tier_a else "B", corroborated=corroborated or tier_a,
                 first_seen=now, last_updated=now)


# --- Gates fire, and do not fire one step below ----------------------------------------

@pytest.mark.parametrize("event, fires", [
    (ev("FR", sev=2, days_ago=29), True),
    (ev("US", sev=2, days_ago=5), True),            # NATO, not EU
    (ev("FR", sev=1, days_ago=5), False),           # one severity too low
    (ev("FR", sev=2, days_ago=31), False),          # one day too old
    (ev("FR", sev=2, corroborated=False), False),   # not corroborated
    (ev("SY", sev=5), False),                       # neither EU nor NATO
    (ev("FR", etype="arrest", sev=2), False),       # not an attack
])
def test_floor_gate(event, fires):
    for region in ("SK", "EU"):
        assert (gates.bounds(region, [event], NOW, CFG).min_level == 2) is fires


@pytest.mark.parametrize("event, lifted", [
    (ev("SK", etype="arrest", sev=1, days_ago=29, sk="direct"), True),   # direct link, 30 days
    (ev("SK", etype="arrest", sev=1, days_ago=31, sk="direct"), False),
    (ev("SK", etype="arrest", sev=1, sk="direct", corroborated=False), False),
    (ev("AT", sev=3, days_ago=13, sk="indirect"), True),                 # attack sev 3, 14 days
    (ev("AT", sev=2, days_ago=13, sk="indirect"), False),
    (ev("AT", sev=3, days_ago=15, sk="indirect"), False),
    (ev("DE", sev=4, days_ago=2, sk="none"), False),                     # no Slovak link
])
def test_sk_cap_at_2(event, lifted):
    b = gates.bounds("SK", [event], NOW, CFG)
    assert (b.max_level > 2) is lifted


@pytest.mark.parametrize("event, lifted", [
    (ev("SK", sev=3, days_ago=1, sk="direct", tier_a=True), True),
    (ev("SK", etype="plot_disrupted", sev=1, days_ago=2, sk="direct", tier_a=True), True),
    (ev("SK", sev=3, days_ago=1, sk="direct", tier_a=False), False),     # no Tier A source
    (ev("SK", sev=3, days_ago=4, sk="direct", tier_a=True), False),      # older than 72 h
    (ev("SK", etype="arrest", sev=1, days_ago=1, sk="direct", tier_a=True), False),
    (ev("AT", sev=5, days_ago=1, sk="indirect", tier_a=True), False),    # not direct
])
def test_sk_cap_at_3(event, lifted):
    assert (gates.bounds("SK", [event], NOW, CFG).max_level == 4) is lifted


@pytest.mark.parametrize("events, lifted", [
    ([ev("FR", sev=5, days_ago=6)], True),
    ([ev("FR", sev=4, days_ago=6)], False),
    ([ev("FR", sev=5, days_ago=8)], False),
    ([ev("FR", sev=3, eid="a"), ev("DE", sev=3, eid="b"), ev("FR", sev=4, eid="c")], True),
    ([ev("FR", sev=3, eid="a"), ev("FR", sev=3, eid="b"), ev("FR", sev=4, eid="c")], False),
    ([ev("FR", sev=3, eid="a"), ev("DE", sev=3, eid="b")], False),
    ([ev("GB", sev=5)], False),                                          # not a member state
])
def test_eu_cap_at_3(events, lifted):
    assert (gates.bounds("EU", events, NOW, CFG).max_level == 4) is lifted


def test_caps_are_shown_only_when_they_lower_the_level():
    b = gates.bounds("SK", [ev("FR", sev=3)], NOW, CFG)
    assert gates.apply(2, b) == (2, [b.floor])
    level, shown = gates.apply(4, b)
    assert level == 2 and [g.id for g in shown] == ["floor_eu_attack_30d", "cap_sk_2"]


def test_disagreement_rule():
    assert not disagree(2, 2) and not disagree(1, 2)
    assert disagree(1, 3) and disagree(2, 3) and disagree(4, 3)


def test_curve_matches_spec():
    assert curve(1, CFG) == pytest.approx(0.375)
    assert curve(2, CFG) == pytest.approx(0.609, abs=1e-3)
    assert curve(10, CFG) == curve(5, CFG)


# --- Replays ---------------------------------------------------------------------------

def anchor(aid, cc, scale, raw):
    lvl = scale.index(raw) + 1
    return AnchorReading(id=aid, country=cc, name=aid, url="https://x", scale=scale, raw=raw,
                         level=lvl, normalized=(lvl - 1) / (len(scale) - 1), as_of=NOW,
                         status="ok")


FCDO = ["cannot be ruled out", "likely", "very likely"]
ANCHORS = [anchor("anchor_sk_sis", "SK", ["1", "2", "3", "4"], "2"),
           anchor("anchor_pl_mswia", "PL", ["ALFA", "BRAVO", "CHARLIE", "DELTA"], "BRAVO"),
           anchor("anchor_fcdo_sk", "SK", FCDO, "cannot be ruled out"),
           anchor("anchor_be_ocam", "BE", ["faible", "moyen", "grave", "tresGrave"], "grave"),
           anchor("anchor_nl_nctv", "NL", ["minimaal", "beperkt", "aanzienlijk", "substantieel",
                                           "kritiek"], "substantieel"),
           anchor("anchor_fcdo_fr", "FR", FCDO, "very likely"),
           anchor("anchor_fcdo_de", "DE", FCDO, "very likely"),
           anchor("anchor_fcdo_at", "AT", FCDO, "likely")]


def quiet_events(now):
    """A normal month: an arrest somewhere in the EU every 4 days, one attack in France."""
    states = ["FR", "DE", "ES", "BE", "IT", "NL", "SE", "AT", "CZ", "PL"]
    evs = [ev(states[i % len(states)], etype="arrest", sev=1, days_ago=4 * i + 1, now=now,
              eid=f"q{now:%m%d}{i}") for i in range(15)]
    return evs + [ev("FR", sev=3, days_ago=18, now=now, eid=f"qfr{now:%m%d}")]


def simulate(incident_days: int, incident=None, quiet_days=30):
    """Run scoring twice a day: quiet_days of quiet, then the incident on its day. Returns
    the scoring per run for each region: [(run time, assessment)]."""
    rows, state, out = [], {"regions": {}, "anchor_history": {}}, {"SK": [], "EU": []}
    start = NOW - timedelta(days=quiet_days + incident_days)
    for n in range(2 * (quiet_days + incident_days)):
        t = start + timedelta(hours=12 * n)
        events = quiet_events(t)
        if incident and t >= NOW - timedelta(days=incident_days):
            events = events + [incident(t)]
        for region in ("SK", "EU"):
            a, row = score_region(region, f"r{n}", events, ANCHORS, {}, rows, state, None, t,
                                  CFG, 0)
            rows.append(row)
            out[region].append((t, a))
    return out


def test_quiet_month_keeps_slovakia_at_level_2_index_30_to_45():
    sk = simulate(0, quiet_days=30)["SK"]
    last = sk[-1][1]
    assert last.level == 2 and 30 <= last.index <= 45, (last.level, last.index)


def _incident(country, sev, sk, tier_a=True, etype="attack"):
    started = {}

    def make(t):
        started.setdefault("at", t)
        days = (t - started["at"]).days
        return ev(country, etype=etype, sev=sev, sk=sk, tier_a=tier_a, now=t, days_ago=days,
                  eid=f"incident_{country}")
    return make


@pytest.mark.parametrize("name, incident, sk_gates, eu_gates", [
    # Bratislava, 12 Oct 2022: two killed, Slovakia. Cap at 2 lifted for Slovakia.
    ("Bratislava 2022", _incident("SK", 4, "direct"), {"cap_sk_2": False}, {}),
    # Vienna, 2 Nov 2020: four killed, a neighbour. Slovakia rises through proximity.
    ("Vienna 2020", _incident("AT", 4, "indirect"), {"cap_sk_2": False},
     {"floor_eu_attack_30d": True}),
    # Solingen, 23 Aug 2024: three killed, no Slovak link. EU signal, Slovak cap stays.
    ("Solingen 2024", _incident("DE", 4, "none"), {}, {"floor_eu_attack_30d": True}),
    # Villach, 15 Feb 2025: one killed, a neighbour.
    ("Villach 2025", _incident("AT", 4, "indirect"), {"cap_sk_2": False},
     {"floor_eu_attack_30d": True}),
])
def test_replays_raise_the_index_within_two_runs(name, incident, sk_gates, eu_gates):
    runs = simulate(2, incident=incident)
    for region, expect in (("SK", sk_gates), ("EU", eu_gates)):
        series = runs[region]
        before = series[-5][1]  # the last run before the incident
        after = [a for _, a in series[-4:-2]]  # the first two runs with it
        assert max(a.index for a in after) > before.index, (name, region, before.index,
                                                             [a.index for a in after])
        gate_ids = {g.id for g in after[-1].gates}
        b = gates.bounds(region, [incident(NOW - timedelta(days=2))], NOW - timedelta(days=2),
                         CFG)
        for gid, present in expect.items():
            if gid == "cap_sk_2":
                assert (b.max_level > 2) is not present, (name, region, gid)
            else:
                assert (gid in gate_ids) is present, (name, region, gid, gate_ids)


def test_bratislava_reaches_level_3_and_drops_back_only_after_hysteresis():
    runs = simulate(2, incident=_incident("SK", 4, "direct"))["SK"]
    assert max(a.level for _, a in runs[-4:]) >= 3
    # Weeks later: a direct-link event from 20 days ago still lifts the cap, but P is back
    # below 0.50 - 0.03. The level waits 4 runs below the threshold before falling.
    rows, state = [], {"regions": {"SK": {"level": 3, "index": 60, "below_runs": 0}},
                       "anchor_history": {}}
    levels = []
    for n in range(6):
        t = NOW + timedelta(hours=12 * n)
        old = ev("SK", etype="arrest", sev=1, sk="direct", days_ago=20, now=t, eid="old_sk")
        a, row = score_region("SK", f"x{n}", quiet_events(t) + [old], ANCHORS, {}, rows, state,
                              None, t, CFG, 0)
        levels.append(a.level)
    assert levels == [3, 3, 3, 2, 2, 2], levels


def test_a_cap_overrides_hysteresis():
    """Gates are hard bounds: with no qualifying event left, the cap applies at once."""
    rows, state = [], {"regions": {"SK": {"level": 3, "index": 60, "below_runs": 0}},
                       "anchor_history": {}}
    a, _ = score_region("SK", "y", quiet_events(NOW), ANCHORS, {}, rows, state, None, NOW, CFG, 0)
    assert a.level == 2 and "cap_sk_2" in {g.id for g in a.gates}
