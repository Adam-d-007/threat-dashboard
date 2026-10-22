import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from pipeline import collect
from pipeline import main as pipeline_main
from pipeline.adapters import base, gdelt_doc, rss
from pipeline.adapters.base import FetchError, FetchResult
from pipeline.health import run_status, source_health
from pipeline.main import FIXTURE_NOW, FIXTURES, window_start
from pipeline.models import Run
from pipeline.process.normalize import canonical_url, clean_text, item_id

NOW = datetime(2026, 10, 22, 11, 0, tzinfo=UTC)
SRC = {"id": "x", "name": "X", "tier": "B", "group": "slovak_press"}


@pytest.mark.parametrize("raw, expected", [
    ("https://WWW.Teraz.sk/a/b/?utm_source=rss&utm_medium=feed", "https://www.teraz.sk/a/b"),
    ("https://example.sk/clanok/1/amp", "https://example.sk/clanok/1"),
    ("https://example.sk/amp/clanok/1", "https://example.sk/clanok/1"),
    ("https://example.sk/clanok.amp?id=3&amp=1#top", "https://example.sk/clanok?id=3"),
    ("https://example.sk/ampere/x", "https://example.sk/ampere/x"),
])
def test_canonical_url(raw, expected):
    assert canonical_url(raw) == expected


def test_clean_text_strips_html_and_truncates():
    assert clean_text("<p>A &amp; <b>B</b></p>") == "A & B"
    long = clean_text("word " * 100)
    assert len(long) == 300 and long.endswith("…")


def test_rss_parse_dates_and_missing_dates():
    tasr = rss.parse((FIXTURES / "tasr.xml").read_bytes())
    assert tasr[0].published_at == datetime(2026, 10, 22, 7, 24, tzinfo=UTC)
    europol = rss.parse((FIXTURES / "europol.xml").read_bytes())
    assert europol[0].published_at is None


def test_rss_rejects_html_page():
    with pytest.raises(FetchError):
        rss.parse(b"<!DOCTYPE html><html><head><title>Security Verification</title></head></html>")


def test_gdelt_parse():
    items = gdelt_doc.parse(json.loads((FIXTURES / "gdelt_doc.json").read_text()))
    assert [i.lang for i in items] == ["sk", "und"]
    assert items[0].published_at == datetime(2026, 10, 22, 7, 15, tzinfo=UTC)


def _response(status):
    return httpx.Response(status, request=httpx.Request("GET", "https://x"))


def test_get_does_not_retry_404(monkeypatch):
    calls = []
    monkeypatch.setattr(httpx, "get", lambda *a, **k: calls.append(1) or _response(404))
    with pytest.raises(FetchError) as e:
        base.get("https://x", backoff_s=0)
    assert e.value.http_status == 404 and len(calls) == 1


def test_get_retries_503_then_succeeds(monkeypatch):
    statuses = iter([503, 429, 200])
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _response(next(statuses)))
    assert base.get("https://x", backoff_s=0).status_code == 200


def test_health_failed_then_stale():
    ok = source_health(SRC, FetchResult("x", ok=True, items=[]), None, NOW)
    assert ok.status == "ok" and ok.last_success == NOW
    prev = ok.model_dump(mode="json")
    failed = source_health(SRC, FetchResult("x", ok=False, error="HTTP 404"), prev,
                           NOW + timedelta(hours=12))
    assert failed.status == "failed" and failed.last_success == NOW
    stale = source_health(SRC, FetchResult("x", ok=False, error="HTTP 404"), prev,
                          NOW + timedelta(hours=49))
    assert stale.status == "stale"
    assert run_status([ok, failed]) == "partial"
    assert run_status([ok]) == "ok"


def test_window_start():
    assert window_start(None, NOW) == NOW - timedelta(hours=36)
    prev = {"run": {"status": "ok", "started_at": "2026-10-22T04:05:00+00:00"}}
    assert window_start(prev, NOW) == datetime(2026, 10, 22, 2, 5, tzinfo=UTC)
    old = {"run": {"status": "ok", "started_at": "2026-10-10T04:05:00+00:00"}}
    assert window_start(old, NOW) == NOW - timedelta(hours=36)


def test_fixture_run_end_to_end(tmp_path):
    msg = tmp_path / "msg.txt"
    assert pipeline_main.main(["--fixtures", "--state-dir", str(tmp_path / "state"),
                               "--commit-msg-file", str(msg)]) == 0
    latest = json.loads((tmp_path / "state" / "latest.json").read_text())
    run = Run.model_validate(latest)
    assert run.run.status == "ok"
    # 8 fetched, the SME copy of the TASR URL is a duplicate, the 12 Oct item is outside the window
    c = run.run.counts
    assert (c.fetched, c.after_dedupe, c.in_window) == (8, 7, 6)
    dup = [i for i in run.items if "fixture-zadrzanie" in i.url]
    assert len(dup) == 1 and dup[0].source_id == "tasr"
    europol = next(i for i in run.items if i.source_id == "europol")
    assert europol.published_estimated and europol.published_at == FIXTURE_NOW
    assert (tmp_path / "state" / "runs" / "2026-10-22T11.json").exists()
    assert msg.read_text() == "run 2026-10-22T11 ok items 6\n"
    seen = json.loads((tmp_path / "state" / "seen.json").read_text())
    assert seen[europol.id] == FIXTURE_NOW.isoformat()


def test_failing_source_gives_partial_run(tmp_path, monkeypatch):
    real = pipeline_main.fixture_fetch

    def broken(src):
        if src["id"] == "sme":
            return FetchResult("sme", ok=False, http_status=404, error="HTTP 404")
        return real(src)

    monkeypatch.setattr(pipeline_main, "fixture_fetch", broken)
    pipeline_main.main(["--fixtures", "--state-dir", str(tmp_path)])
    run = Run.model_validate_json((tmp_path / "latest.json").read_text())
    assert run.run.status == "partial"
    sme = next(s for s in run.sources if s.id == "sme")
    # never succeeded before, so it is stale rather than merely failed
    assert sme.status == "stale" and sme.error == "HTTP 404"
    assert all(s.status == "ok" for s in run.sources if s.id != "sme")


def test_crashing_adapter_does_not_stop_run(tmp_path, monkeypatch):
    real = pipeline_main.fixture_fetch

    def crash(src):
        if src["id"] == "europol":
            raise RuntimeError("boom")
        return real(src)

    monkeypatch.setattr(pipeline_main, "fixture_fetch", crash)
    pipeline_main.main(["--fixtures", "--state-dir", str(tmp_path)])
    run = Run.model_validate_json((tmp_path / "latest.json").read_text())
    europol = next(s for s in run.sources if s.id == "europol")
    assert run.run.status == "partial" and "boom" in europol.error


def _buffer(path):
    return json.loads((path / "rss_buffer.json").read_text())


def test_collect_builds_and_keeps_buffer(tmp_path):
    msg = tmp_path / "msg.txt"
    assert collect.main(["--fixtures", "--state-dir", str(tmp_path),
                         "--commit-msg-file", str(msg)]) == 0
    items = _buffer(tmp_path)["items"]
    # RSS fixtures only: TASR 3 + SME 2 + Europol 1, minus the SME copy of a TASR URL
    assert len(items) == 5 and not any(i["source_id"] == "gdelt_doc" for i in items)
    assert msg.read_text() == "collect 2026-10-22T11:00 +5 new, 5 buffered\n"
    # A second collection adds nothing and keeps the first fetch time.
    collect.main(["--fixtures", "--state-dir", str(tmp_path), "--commit-msg-file", str(msg)])
    assert msg.read_text() == "collect 2026-10-22T11:00 +0 new, 5 buffered\n"
    assert _buffer(tmp_path)["items"] == items
    # The collector writes nothing but the buffer.
    assert sorted(p.name for p in tmp_path.iterdir()) == ["msg.txt", "rss_buffer.json"]


def test_collect_prunes_items_older_than_48h(tmp_path):
    collect.main(["--fixtures", "--state-dir", str(tmp_path)])
    data = _buffer(tmp_path)
    data["items"][0]["fetched_at"] = (FIXTURE_NOW - timedelta(hours=49)).isoformat()
    data["items"][0]["id"] = "old-id"
    data["items"][1]["fetched_at"] = (FIXTURE_NOW - timedelta(hours=47)).isoformat()
    (tmp_path / "rss_buffer.json").write_text(json.dumps(data))
    collect.main(["--fixtures", "--state-dir", str(tmp_path)])
    ids = {i["id"] for i in _buffer(tmp_path)["items"]}
    assert "old-id" not in ids and data["items"][1]["id"] in ids


def test_collect_replaces_invalid_buffer(tmp_path):
    (tmp_path / "rss_buffer.json").write_text('{"schema_version": 1, "items": "garbage"}')
    msg = tmp_path / "msg.txt"
    collect.main(["--fixtures", "--state-dir", str(tmp_path), "--commit-msg-file", str(msg)])
    assert len(_buffer(tmp_path)["items"]) == 5
    assert msg.read_text().endswith(", invalid buffer replaced\n")


def _buffered_item(**overrides):
    item = {
        "id": "buffered-1", "source_id": "tasr", "tier": "B",
        "url": "https://www.teraz.sk/slovensko/scrolled-off/1000009-clanok.html",
        "title": "Item that scrolled off the feed before the run", "lang": "sk",
        "published_at": "2026-10-22T02:00:00Z", "published_estimated": False,
        "fetched_at": "2026-10-22T02:35:00Z", "snippet": "", "domain": "teraz.sk",
        "also_reported_by": [], "gdelt": None,
    }
    return item | overrides


def test_pipeline_merges_buffer(tmp_path):
    (tmp_path / "rss_buffer.json").write_text(json.dumps({
        "schema_version": 1, "updated_at": "2026-10-22T10:35:00Z",
        "items": [_buffered_item(),
                  _buffered_item(id="other", source_id="not_a_source", url="https://x.sk/a")],
    }))
    pipeline_main.main(["--fixtures", "--state-dir", str(tmp_path)])
    run = Run.model_validate_json((tmp_path / "latest.json").read_text())
    assert run.run.counts.from_buffer == 1  # items from unknown or disabled sources are ignored
    assert any(i.id == "buffered-1" for i in run.items)
    assert run.run.status == "ok"
    # The pipeline reads the buffer but never rewrites it.
    assert _buffer(tmp_path)["updated_at"] == "2026-10-22T10:35:00Z"


def test_pipeline_keeps_earlier_estimated_date_from_buffer(tmp_path):
    collect_time = FIXTURE_NOW - timedelta(hours=5)
    europol = rss.parse((FIXTURES / "europol.xml").read_bytes())[0]
    eid = item_id(canonical_url(europol.url))
    (tmp_path / "rss_buffer.json").write_text(json.dumps({
        "schema_version": 1, "updated_at": collect_time.isoformat(),
        "items": [_buffered_item(id=eid, source_id="europol", tier="A", url=europol.url,
                                 published_at=collect_time.isoformat(),
                                 published_estimated=True, fetched_at=collect_time.isoformat())],
    }))
    pipeline_main.main(["--fixtures", "--state-dir", str(tmp_path)])
    run = Run.model_validate_json((tmp_path / "latest.json").read_text())
    item = next(i for i in run.items if i.id == eid)
    assert item.published_at == collect_time
    seen = json.loads((tmp_path / "seen.json").read_text())
    assert seen[eid] == collect_time.isoformat()


def test_invalid_buffer_makes_run_partial_not_failed(tmp_path):
    (tmp_path / "rss_buffer.json").write_text('{"schema_version": 1, "items": "garbage"}')
    pipeline_main.main(["--fixtures", "--state-dir", str(tmp_path)])
    run = Run.model_validate_json((tmp_path / "latest.json").read_text())
    assert run.run.status == "partial" and run.run.counts.in_window == 6
