"""What each stage did and whether the run counts as ok, in facts rather than one word.

The run is ok when enough press sources are fresh, no article has waited too long for a label,
the last scoring used a model's assessment for both regions and is recent, and every theatre
that had news got its text. Anything else is degraded, with the reason in words; a stage that
crashed makes it failed.
"""

from datetime import datetime, timedelta

from pipeline.health import PRESS
from pipeline.models import SourceHealth, Terrorism

from .incidents import needs_match
from .labelling import waiting
from .models import Article, Queue, Stage, Status


def queue(articles: dict[str, Article], cfg_match: dict, now: datetime) -> Queue:
    day = now - timedelta(hours=24)
    wait = waiting(articles)
    oldest = min((a.first_seen for a in wait), default=None)
    return Queue(
        waiting_label=len(wait),
        waiting_match=sum(1 for a in articles.values() if needs_match(a, cfg_match)),
        oldest_waiting_hours=round((now - oldest).total_seconds() / 3600, 1) if oldest else None,
        given_up_24h=sum(1 for a in articles.values() if a.given_up and a.first_seen >= day),
        labelled_24h=sum(1 for a in articles.values() if a.labelled_at and a.labelled_at >= day))


def labelled_by(articles: dict[str, Article], now: datetime) -> dict[str, int]:
    day = now - timedelta(hours=24)
    out: dict[str, int] = {}
    for a in articles.values():
        if a.labelled_at and a.labelled_at >= day:
            out[a.labelled_by] = out.get(a.labelled_by, 0) + 1
    return out


def reasons(q: Queue, sources: list[SourceHealth], terrorism: Terrorism | None,
            scored_at: datetime | None, stale_theatres: list[str], ai_on: bool, now: datetime,
            cfg: dict) -> list[str]:
    """Why the run is not ok; empty when it is."""
    out = []
    if not ai_on:
        out.append("the AI is switched off or has no key")
    press = sum(1 for s in sources if s.group in PRESS and s.tier == "B" and s.status == "ok")
    if press < cfg["min_press_ok"]:
        out.append(f"only {press} press sources are fresh (at least {cfg['min_press_ok']} needed)")
    if q.oldest_waiting_hours is not None and q.oldest_waiting_hours > cfg["max_wait_hours"]:
        out.append(f"an article has waited {q.oldest_waiting_hours:.0f} hours for a label")
    if terrorism is None or scored_at is None:
        out.append("no threat level has been computed yet")
    else:
        if now - scored_at > timedelta(hours=cfg["max_score_hours"]):
            out.append(f"the threat level was last computed {scored_at:%d %b %H:%M} UTC")
        blind = [r for r in ("SK", "EU") if getattr(terrorism, r).llm.status != "ok"]
        if blind:
            out.append("the last scoring had no model assessment for " + " and ".join(blind))
    if stale_theatres:
        out.append("the brief was not written for: " + ", ".join(stale_theatres))
    return out


def build(now: datetime, started: datetime, git_sha: str | None, stages: dict[str, Stage],
          articles: dict[str, Article], sources: list[SourceHealth],
          terrorism: Terrorism | None, scored_at: datetime | None, last_scored: str | None,
          stale_theatres: list[str], brief_written_at: datetime | None, ai, cfg: dict) -> Status:
    q = queue(articles, cfg["match"], now)
    why = reasons(q, sources, terrorism, scored_at, stale_theatres, ai is not None, now,
                  cfg["status"])
    crashed = [f"{name} failed: {s.detail}" for name, s in stages.items() if s.status == "failed"]
    return Status(
        schema_version=2, updated_at=now, started_at=started, git_sha=git_sha,
        overall="failed" if crashed else ("degraded" if why else "ok"), reasons=crashed + why,
        stages=stages, queue=q, ai=ai.report() if ai is not None else {},
        labelled_by_24h=labelled_by(articles, now), last_scored=last_scored,
        brief_written_at=brief_written_at, sources=sources)


def alert_due(log: list[dict], now: datetime, hours: float) -> bool:
    """True when the runs have been recorded for at least `hours` and none in that time was
    ok: the one condition that opens the GitHub issue."""
    since = now - timedelta(hours=hours)
    times = [(datetime.fromisoformat(e["at"]), e["overall"]) for e in log]
    return bool(times) and min(t for t, _ in times) <= since and not any(
        t >= since and overall == "ok" for t, overall in times)
