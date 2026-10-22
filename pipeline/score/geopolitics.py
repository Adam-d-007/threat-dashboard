"""Geopolitics tab: activity against normal per theatre (never a threat level), the daily
brief, top developments, the Slovak angle and the watchlist. There is no official scale to
anchor a geopolitical "threat" to, so the tab measures activity only."""

import json
import logging
from datetime import date, datetime, timedelta
from statistics import median

import yaml
from pydantic import ValidationError

from ..llm.client import LlmBadOutput, LlmClient, LlmUnavailable
from ..llm.prompts import BRIEF_SYSTEM, brief_user, retry_user
from ..llm.schemas import BriefOut
from ..models import (
    Activity,
    Brief,
    BriefLine,
    Geopolitics,
    Item,
    Theatre,
    TopItem,
    WatchlistEntry,
)
from .components import curve

log = logging.getLogger("pipeline.geopolitics")
MAX_BRIEF_ITEMS = 120


def daily_activity(baselines: dict, spec: dict, day: str) -> int:
    day_counts = baselines.get("gkg", {}).get("daily", {}).get(day, {})
    return sum(day_counts.get(theme, {}).get(cc, 0)
               for theme in spec["themes"] for cc in spec["countries"])


def activity(baselines: dict, spec: dict, now: datetime, cfg: dict) -> tuple[Activity, list]:
    """(activity on the latest complete day against its 90-day median, 30-day sparkline)."""
    mc = cfg["media"]
    files = baselines.get("gkg", {}).get("files_per_day", {})
    today = now.strftime("%Y-%m-%d")
    complete = sorted(d for d, n in files.items() if n >= mc["min_files_per_day"] and d < today)
    if not complete:
        return Activity(value=None), []
    counts = {d: daily_activity(baselines, spec, d) for d in complete}
    latest = complete[-1]
    start = (date.fromisoformat(latest) - timedelta(days=mc["baseline_days"])).isoformat()
    history = [counts[d] for d in complete[:-1] if d >= start]
    if len(history) < mc["min_history_days"]:
        return Activity(value=None, articles_24h=counts[latest]), []
    base = max(median(history), mc["floor"])
    spark = [round(curve(counts[d] / base, cfg), 3) for d in complete[-30:]]
    return Activity(value=round(curve(counts[latest] / base, cfg), 4),
                    articles_24h=counts[latest], baseline_median=float(median(history))), spark


def _item_row(i: Item) -> dict:
    c = i.classification
    return {"id": i.id, "source": i.domain, "date": i.published_at.date().isoformat(),
            "domain": c.domain if c else None, "countries": c.countries if c else [],
            "sk_link": c.sk_link if c else None,
            "summary": (c.summary_en if c and c.summary_en else i.title)}


def write_brief(items: list[Item], theatres: list[dict], previous: list[str],
                client: LlmClient | None, now: datetime, call_limit: int) -> BriefOut | None:
    if client is None or not client.available or client.calls >= call_limit or not items:
        return None
    rows = [_item_row(i) for i in items[:MAX_BRIEF_ITEMS]]
    user = brief_user(rows, [{"id": t["id"], "name": t["name_en"]} for t in theatres],
                      previous, now.date().isoformat())
    prompt = user
    for attempt in (1, 2):
        try:
            return BriefOut.model_validate(json.loads(client.complete_json(BRIEF_SYSTEM, prompt)))
        except LlmUnavailable:
            return None
        except (json.JSONDecodeError, ValidationError, LlmBadOutput) as e:
            if attempt == 2:
                log.warning("brief failed twice: %s", str(e)[:200])
                return None
            prompt = retry_user(user, str(e))
    return None


def watchlist(path, out: BriefOut | None, known: set[str], now: datetime) -> list[WatchlistEntry]:
    """Hand-entered dates (verified) plus dates from the news (unverified), future only."""
    today = now.date()
    entries = []
    for e in (yaml.safe_load(path.read_text()) or {}).get("events") or []:
        d = e["date"] if isinstance(e["date"], date) else date.fromisoformat(str(e["date"]))
        if d >= today:
            entries.append(WatchlistEntry(date=d, title_en=e["title_en"],
                                          title_sk=e.get("title_sk"), origin="manual",
                                          verified=True, url=e.get("url")))
    manual_days = {e.date for e in entries}
    for u in (out.upcoming if out else []):
        d = date.fromisoformat(u.date)
        if d >= today and u.item_id in known and d not in manual_days:
            entries.append(WatchlistEntry(date=d, title_en=u.title_en, title_sk=u.title_sk,
                                          origin="news", verified=False))
    return sorted(entries, key=lambda e: e.date)[:15]


def build(items: list[Item], prev_items: list[dict], prev_brief: list[str], baselines: dict,
          client: LlmClient | None, now: datetime, cfg: dict, config_dir, call_limit: int,
          ) -> Geopolitics:
    theatres_cfg = yaml.safe_load((config_dir / "theatres.yaml").read_text())["theatres"]
    pool = [i for i in items if i.classification and i.classification.relevant]
    out = write_brief(pool, theatres_cfg, prev_brief, client, now, call_limit)
    known = {i.id for i in pool} | {p["id"] for p in prev_items}
    by_theatre = {t.id: t for t in (out.theatres if out else [])}
    theatres = []
    for t in theatres_cfg:
        act, spark = activity(baselines, t["activity"], now, cfg)
        got = by_theatre.get(t["id"])
        theatres.append(Theatre(
            id=t["id"], name_en=t["name_en"], name_sk=t["name_sk"], activity=act,
            sparkline=spark,
            top_items=[TopItem(item_id=x.item_id, summary_en=x.summary_en,
                               summary_sk=x.summary_sk)
                       for x in (got.top_items if got else []) if x.item_id in known],
            sk_angle_en=got.sk_angle_en if got else None,
            sk_angle_sk=got.sk_angle_sk if got else None))
    brief = None
    if out:
        lines = [BriefLine(text_en=line.text_en, text_sk=line.text_sk,
                           item_ids=[x for x in line.item_ids if x in known])
                 for line in out.lines]
        brief = Brief(status="ok", lines=[x for x in lines if x.item_ids],
                      what_changed_en=out.what_changed_en, what_changed_sk=out.what_changed_sk)
    elif client is not None and client.providers:
        brief = Brief(status="fallback")
    return Geopolitics(theatres=theatres, brief=brief,
                       watchlist=watchlist(config_dir / "watchlist.yaml", out, known, now))
