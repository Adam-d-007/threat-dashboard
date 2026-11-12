import copy
import json
from datetime import UTC, date, datetime
from types import SimpleNamespace

import yaml

from monitor.ai.client import AiUnavailable
from monitor.incidents import seed
from monitor.scoring import assessor, due_slot, score
from monitor.tests.helpers import FakeAi
from monitor.tests.test_incidents import v1_event
from pipeline.main import CONFIG
from pipeline.process.normalize import item_id
from pipeline.score.terrorism import score_region, update_anchor_history

CFG = yaml.safe_load((CONFIG / "scoring.yaml").read_text())
NOW = datetime(2026, 11, 12, 14, 30, tzinfo=UTC)
SLOTS = {"04": 5, "13": 14}


def test_a_slot_runs_from_its_hour_on_and_only_once():
    def at(hour):
        return NOW.replace(hour=hour)
    assert due_slot(at(4), SLOTS, []) is None
    assert due_slot(at(5), SLOTS, []) == "2026-11-12T04"
    assert due_slot(at(9), SLOTS, [{"run_id": "2026-11-12T04"}]) is None
    assert due_slot(at(14), SLOTS, [{"run_id": "2026-11-12T04"}]) == "2026-11-12T13"
    # GitHub skipped the hours from 14 to 19: the slot still runs, late.
    assert due_slot(at(20), SLOTS, [{"run_id": "2026-11-12T04"}]) == "2026-11-12T13"
    assert due_slot(at(20), SLOTS, [{"run_id": "2026-11-12T13"}]) is None


def history():
    """Fifteen days of earlier runs, so E has its baseline."""
    return [{"run_id": f"2026-10-{d:02d}T04", "at": f"2026-10-{d:02d}T04:05:00+00:00",
             "region": r, "index": 30, "level": 2, "rules_level": 2, "llm_level": None,
             "components": {"events_raw": 3.0}} for d in range(15, 31) for r in ("SK", "EU")]


def events():
    return [v1_event("evt_aaa", 5), v1_event("evt_bbb", 0, event_type="other"),
            v1_event("evt_ccc", 1, event_type="arrest", country="SK", sk_link="direct",
                     date=date(2026, 11, 10)),
            v1_event("evt_ddd", 3, country="UA", topic=None)]


def test_carried_over_incidents_score_exactly_as_the_old_events_did():
    state = {"regions": {"SK": {"level": 2, "index": 30, "below_runs": 0},
                         "EU": {"level": 2, "index": 30, "below_runs": 0}}, "anchor_history": {}}
    old_state, old_rows = copy.deepcopy(state), history()
    update_anchor_history(old_state, [], NOW)
    old = {r: score_region(r, "run", events(), [], {}, old_rows, old_state, None, NOW, CFG, 0)
           for r in ("SK", "EU")}
    new_state, new_rows = copy.deepcopy(state), history()
    incidents = seed(events(), [], NOW, 90, item_id)
    new = score("run", incidents, [], {}, new_rows, new_state, None, NOW, CFG, 25)
    for region in ("SK", "EU"):
        a, row = old[region]
        b = getattr(new, region)
        assert (b.index, b.level, b.rules_level, b.provisional) == (
            a.index, a.level, a.rules_level, a.provisional)
        assert [c.value for c in b.components] == [c.value for c in a.components]
        assert [g.id for g in b.gates] == [g.id for g in a.gates]
        assert new_rows[-2 if region == "SK" else -1]["components"] == row["components"]
    assert new_state["regions"] == old_state["regions"]
    assert new.SK.llm.status == "disabled"


def assessment(**over) -> str:
    return json.dumps({"level": 2, "position": "mid", "confidence": "medium",
                       "what_changed_en": "Little.", "what_changed_sk": "Málo.",
                       "drivers": [{"text_en": "An attack in Kraków.",
                                    "text_sk": "Útok v Krakove.", "event_ids": ["inc_aaa", "inc_zzz"]},
                                   {"text_en": "Made up.", "text_sk": "Vymyslené.",
                                    "event_ids": ["inc_zzz"]}]} | over)


class Models(FakeAi):
    def __init__(self, *answers):
        super().__init__(*answers)
        self.models["gemini_36"] = SimpleNamespace(model="gemini-3.6-flash")


def test_the_models_assessment_counts_and_records_which_model_gave_it():
    incidents = seed(events(), [], NOW, 90, item_id)
    state = {"regions": {}, "anchor_history": {}}
    ai = Models((assessment(), "gemini_36"), (assessment(level=3, position="low"), "gemini_36"))
    result = score("run", incidents, [], {}, history(), state, ai, NOW, CFG, 25)
    llm = result.SK.llm
    assert (llm.status, llm.level, llm.model) == ("ok", 2, "gemini-3.6-flash")
    # A driver may only rest on incidents the model was shown.
    assert [d.event_ids for d in llm.drivers] == [["inc_aaa"]]
    assert result.EU.llm.level == 3
    assert [a["task"] for a in ai.asked] == ["assess", "assess"]
    sent = json.loads(ai.asked[0]["user"].split("\n", 1)[1].rsplit("\n", 1)[0])
    assert {e["id"] for e in sent["events_last_60_days"]} <= {"inc_aaa", "inc_ccc", "inc_ddd"}


def test_without_an_answer_the_level_rests_on_the_other_components():
    incidents = seed(events(), [], NOW, 90, item_id)
    ai = Models(AiUnavailable("down"), AiUnavailable("down"))
    result = score("run", incidents, [], {}, history(), {"regions": {}, "anchor_history": {}},
                   ai, NOW, CFG, 25)
    assert result.SK.llm.status == "fallback"
    assert next(c for c in result.SK.components if c.id == "llm").value is None


def test_only_the_strongest_incidents_are_shown_to_the_model():
    user_sizes = []

    class Count(Models):
        def ask(self, task, system, user, *a, **k):
            user_sizes.append(len(json.loads(user.split("\n", 1)[1].rsplit("\n", 1)[0])[
                "events_last_60_days"]))
            raise AiUnavailable("down")
    many = [v1_event(f"evt_{n:03d}", 3, country="FR") for n in range(40)]
    assessor(Count(), 25)("EU", None, [(e, 1.0) for e in many], [], {}, [], 0)
    assert user_sizes == [25]
