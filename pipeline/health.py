"""Source health records and the run status."""

from datetime import datetime, timedelta

from .adapters.base import FetchResult
from .models import RunStatus, SourceHealth

STALE_AFTER = timedelta(hours=48)
STALE_ZERO_RUNS = 6
PRESS = {"slovak_press", "regional_press", "eu_press"}
MIN_PRESS_OK = 10


def _dt(previous: dict | None, key: str) -> datetime | None:
    return datetime.fromisoformat(previous[key]) if previous and previous.get(key) else None


def source_health(source: dict, result: FetchResult | None, previous: dict | None,
                  now: datetime) -> SourceHealth:
    """result is None for a disabled source. previous is last run's record for this source.

    Stale: no successful fetch for 48 h, or 6 successful runs in a row with no items from a
    source that has delivered items before (sources that only produce counts never are)."""
    base = {"id": source["id"], "name": source["name"], "tier": source["tier"],
            "group": source["group"]}
    last_success, last_error = _dt(previous, "last_success"), _dt(previous, "last_error")
    last_items_at = _dt(previous, "last_items_at")
    if result is None:
        return SourceHealth(**base, status="disabled", last_success=last_success,
                            last_error=last_error, items=0, note=source.get("notes"),
                            last_items_at=last_items_at)
    if result.ok:
        items = result.item_count if result.item_count is not None else len(result.items)
        zero_runs = 0 if items else (previous or {}).get("zero_runs", 0) + 1
        if items:
            last_items_at = now
        empty = zero_runs >= STALE_ZERO_RUNS and last_items_at is not None
        return SourceHealth(**base, status="stale" if empty else "ok", last_success=now,
                            last_error=last_error, items=items, http_status=result.http_status,
                            error=f"no items for {zero_runs} runs" if empty else result.error,
                            zero_runs=zero_runs, last_items_at=last_items_at)
    stale = last_success is None or now - last_success > STALE_AFTER
    return SourceHealth(**base, status="stale" if stale else "failed",
                        last_success=last_success, last_error=now, items=len(result.items),
                        http_status=result.http_status, error=result.error,
                        zero_runs=(previous or {}).get("zero_runs", 0),
                        last_items_at=last_items_at)


def run_status(health: list[SourceHealth], llm_status: str) -> RunStatus:
    """ok when every enabled source succeeded and, as the spec's status table requires, GDELT
    DOC, the LLM and at least 10 Tier B press sources did; otherwise partial. (The spec's phase 2
    check, one 404 source makes the run partial, needs the first condition.) An LLM switched off
    on purpose (--no-llm) does not make a run partial."""
    if any(h.status in ("failed", "stale") for h in health):
        return "partial"
    by_id = {h.id: h for h in health}
    gdelt_ok = by_id.get("gdelt_doc") is None or by_id["gdelt_doc"].status == "ok"
    press_ok = sum(1 for h in health if h.group in PRESS and h.tier == "B" and h.status == "ok")
    ok = gdelt_ok and llm_status in ("ok", "disabled") and press_ok >= MIN_PRESS_OK
    return "ok" if ok else "partial"
