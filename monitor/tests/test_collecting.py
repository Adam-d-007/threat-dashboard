import json
from datetime import timedelta

import pytest

from monitor import collecting, store
from monitor.tests.helpers import NOW
from pipeline.adapters.base import FetchResult, RawItem
from pipeline.models import AnchorReading
from pipeline.store import state as buffer_store


def src(sid, adapter="rss", **over):
    return {"id": sid, "name": sid.upper(), "group": "slovak_press", "tier": "B", "lang": "sk",
            "adapter": adapter, "urls": [f"https://{sid}.example/feed"], "enabled": True} | over


SOURCES = [src("tasr"), src("gdelt_doc", "gdelt_doc", tier="C", group="backbone"),
           src("sis_news", "html_scrape", tier="A", group="official"),
           src("minv", hourly=False, tier="A", group="official"),
           src("gkg", "gdelt_gkg", tier="C", group="backbone"),
           src("old_feed", enabled=False)]
READING = AnchorReading(id="anchor_sk_sis", country="SK", name="SIS NBAC",
                        url="https://www.sis.gov.sk", scale=["1", "2", "3", "4"], raw="2",
                        level=2, normalized=0.333, as_of=NOW, status="ok")


class Network:
    """The adapters, the official-level reader and the media counts, replaced."""

    def __init__(self, monkeypatch, failing=()):
        self.fetched, self.anchors_read, self.gkg = [], [], 0
        self.failing = set(failing)

        def fetch_all(sources, queries, since, now, fixtures):
            out = {}
            for s in sources:
                self.fetched.append(s["id"])
                if s["id"] in self.failing:
                    out[s["id"]] = FetchResult(source_id=s["id"], ok=False, error="HTTP 503")
                    continue
                undated = s["id"] == "sis_news"
                out[s["id"]] = FetchResult(source_id=s["id"], ok=True, http_status=200, items=[
                    RawItem(url=f"https://{s['id']}.example/{now:%H}", title=f"Útok {s['id']} {now:%H}",
                            published_at=None if undated else now - timedelta(minutes=5))])
            return out

        def read_all(previous, now):
            self.anchors_read.append([a["id"] for a in previous])
            return [READING.model_copy(update={"as_of": now})]

        def run_gkg(source, baselines, now):
            self.gkg += 1
            baselines["gkg"]["processed"].append(f"{now:%Y%m%d%H}0000")
            return FetchResult(source_id=source["id"], ok=True, http_status=200)

        monkeypatch.setattr(collecting.old_main, "fetch_all", fetch_all)
        monkeypatch.setattr(collecting.anchor_reader, "read_all", read_all)
        monkeypatch.setattr(collecting.old_main, "run_gkg", run_gkg)


def by_id(health):
    return {h.id: h for h in health}


def test_an_ordinary_hour_fetches_the_feeds_and_gdelt_only(tmp_path, monkeypatch):
    net = Network(monkeypatch)
    health, anchors, stats = collecting.collect(tmp_path, SOURCES, [], NOW, slot=False)
    assert net.fetched == ["tasr", "gdelt_doc"] and net.anchors_read == [] and net.gkg == 0
    assert stats == {"new": 2, "buffered": 2, "failed": [], "buffer_reset": False}
    assert {i.source_id for i in buffer_store.load_buffer(tmp_path)} == {"tasr", "gdelt_doc"}
    h = by_id(health)
    assert h["tasr"].status == "ok" and h["tasr"].items == 1
    assert h["old_feed"].status == "disabled"
    assert "sis_news" not in h  # never fetched yet, so nothing to report
    assert anchors == [] and not (tmp_path / "baselines.json").exists()


def test_a_scoring_hour_also_reads_the_pages_the_official_levels_and_media_counts(
        tmp_path, monkeypatch):
    net = Network(monkeypatch)
    (tmp_path / "latest.json").write_text(json.dumps({"anchors": [READING.model_dump(mode="json")]}))
    health, anchors, stats = collecting.collect(tmp_path, SOURCES, [], NOW, slot=True)
    assert net.fetched == ["tasr", "gdelt_doc", "sis_news", "minv"]
    assert net.anchors_read == [["anchor_sk_sis"]] and net.gkg == 1
    assert [a.as_of for a in anchors] == [NOW]
    assert json.loads((tmp_path / "baselines.json").read_text())["gkg"]["processed"] == [
        f"{NOW:%Y%m%d%H}0000"]
    assert stats["new"] == 4
    h = by_id(health)
    assert {k: v.status for k, v in h.items()} == {
        "tasr": "ok", "gdelt_doc": "ok", "sis_news": "ok", "minv": "ok", "gkg": "ok",
        "old_feed": "disabled"}
    # An undated item keeps the moment it was first seen.
    seen = store.load_json(tmp_path, "seen.json", {})
    assert len(seen) == 1 and list(seen.values()) == [NOW.isoformat()]

    # The next, ordinary hour keeps the twice-daily sources' records as they were.
    later = NOW + timedelta(hours=1)
    health2, _, _ = collecting.collect(tmp_path, SOURCES, [], later, slot=False)
    assert by_id(health2)["sis_news"] == h["sis_news"]
    assert by_id(health2)["tasr"].last_success == later


def test_a_feed_that_fails_for_an_hour_is_not_an_alarm_but_one_down_all_day_is(
        tmp_path, monkeypatch):
    Network(monkeypatch)
    collecting.collect(tmp_path, SOURCES, [], NOW, slot=False)
    Network(monkeypatch, failing={"tasr"})
    health, _, stats = collecting.collect(tmp_path, SOURCES, [], NOW + timedelta(hours=1),
                                          slot=False)
    assert stats["failed"] == ["tasr"] and by_id(health)["tasr"].status == "ok"
    health, _, _ = collecting.collect(tmp_path, SOURCES, [], NOW + timedelta(hours=8),
                                      slot=False)
    assert by_id(health)["tasr"].status == "failed"


def test_items_older_than_two_days_leave_the_buffer_and_repeats_are_kept_once(
        tmp_path, monkeypatch):
    Network(monkeypatch)
    collecting.collect(tmp_path, SOURCES, [], NOW, slot=False)
    collecting.collect(tmp_path, SOURCES, [], NOW, slot=False)  # the same items again
    assert len(buffer_store.load_buffer(tmp_path)) == 2
    collecting.collect(tmp_path, SOURCES, [], NOW + timedelta(hours=49), slot=False)
    assert {i.fetched_at for i in buffer_store.load_buffer(tmp_path)} == {
        NOW + timedelta(hours=49)}


def test_a_broken_buffer_is_started_again_and_the_run_says_so(tmp_path, monkeypatch):
    Network(monkeypatch)
    (tmp_path / "rss_buffer.json").write_text('{"items": "broken"}')
    _, _, stats = collecting.collect(tmp_path, SOURCES, [], NOW, slot=False)
    assert stats["buffer_reset"] is True and stats["buffered"] == 2


def test_the_shipped_sources_split_into_hourly_and_twice_daily_as_before():
    from pipeline.main import load_config
    sources, _ = load_config()
    on = [s for s in sources if s["enabled"]]
    assert {s["adapter"] for s in on if collecting.hourly(s)} == {"rss", "gdelt_doc"}
    assert "minv" not in {s["id"] for s in on if collecting.hourly(s)}


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level("WARNING")
