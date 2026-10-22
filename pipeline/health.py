"""Source health records and the run status."""

from datetime import datetime, timedelta

from .adapters.base import FetchResult
from .models import RunStatus, SourceHealth

STALE_AFTER = timedelta(hours=48)


def source_health(source: dict, result: FetchResult | None, previous: dict | None,
                  now: datetime) -> SourceHealth:
    """result is None for a disabled source. previous is last run's record for this source."""
    base = {"id": source["id"], "name": source["name"], "tier": source["tier"],
            "group": source["group"]}
    last_success = (datetime.fromisoformat(previous["last_success"])
                    if previous and previous.get("last_success") else None)
    last_error = (datetime.fromisoformat(previous["last_error"])
                  if previous and previous.get("last_error") else None)
    if result is None:
        return SourceHealth(**base, status="disabled", last_success=last_success,
                            last_error=last_error, items=0, note=source.get("notes"))
    if result.ok:
        return SourceHealth(**base, status="ok", last_success=now, last_error=last_error,
                            items=len(result.items), http_status=result.http_status)
    stale = last_success is None or now - last_success > STALE_AFTER
    return SourceHealth(**base, status="stale" if stale else "failed",
                        last_success=last_success, last_error=now, items=len(result.items),
                        http_status=result.http_status, error=result.error)


def run_status(health: list[SourceHealth]) -> RunStatus:
    """Phase 1 rule: ok when every enabled source succeeded, otherwise partial.

    Phase 3 replaces this with the full rule (GDELT DOC, the LLM and at least
    10 Tier B press sources must succeed).
    """
    enabled = [h for h in health if h.status != "disabled"]
    return "ok" if all(h.status == "ok" for h in enabled) else "partial"
