"""Stage 6, the geopolitics page: activity against normal per theatre (the old pipeline's
measure, unchanged) and the brief, written one theatre at a time so each call fits the free
providers' limits. A theatre whose call fails keeps its previous text with the time it was
really written; text older than keep_hours is dropped rather than shown as current.
"""

import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from pipeline.models import BriefLine, TopItem, WatchlistEntry
from pipeline.process.prefilter import TIER_ORDER
from pipeline.score import geopolitics as old

from .ai.client import AiUnavailable
from .ai.tasks import BRIEF_SCHEMA, BRIEF_SYSTEM, TheatreBrief, brief_user, parse_brief
from .models import Article, GeopoliticsFile, TheatreV2

log = logging.getLogger("monitor.brief")
MAX_WATCHLIST = 15


def theatre_reports(articles: dict[str, Article], countries: list[str], domains: list[str],
                    now: datetime, cfg: dict) -> list[Article]:
    """A theatre's reports of the last window_hours: labelled relevant, in one of its domains
    and naming one of its countries; official sources first, then the newest."""
    since = now - timedelta(hours=cfg["window_hours"])
    pool = [a for a in articles.values()
            if a.label and a.label.kind != "none" and a.published_at >= since
            and a.label.domain in domains and set(a.label.countries) & set(countries)]
    pool.sort(key=lambda a: (TIER_ORDER[a.tier], -a.published_at.timestamp()))
    return pool[:cfg["max_reports"]]


def _row(short: str, a: Article) -> dict:
    return {"id": short, "source": a.domain, "date": a.published_at.date().isoformat(),
            "kind": a.label.kind, "countries": a.label.countries, "sk_link": a.label.sk_link,
            "summary": a.label.summary_en}


def _written(t: TheatreV2, out: TheatreBrief, by_short: dict[str, Article], model: str,
             now: datetime) -> list[WatchlistEntry]:
    """Put a model's answer on the theatre; returns the dated events it found. Lines and items
    citing a report that was not sent are dropped."""
    t.lines = [BriefLine(text_en=line.text_en, text_sk=line.text_sk,
                         item_ids=[by_short[i].id for i in ids],
                         urls=[by_short[i].url for i in ids])
               for line in out.lines
               for ids in [[i for i in line.item_ids if i in by_short]] if ids]
    t.top_items = [TopItem(item_id=by_short[x.item_id].id, summary_en=x.summary_en,
                           summary_sk=x.summary_sk)
                   for x in out.top_items if x.item_id in by_short]
    t.sk_angle_en, t.sk_angle_sk = out.sk_angle_en, out.sk_angle_sk
    t.written_at, t.written_by = now, model
    return [WatchlistEntry(date=date.fromisoformat(u.date), title_en=u.title_en,
                           title_sk=u.title_sk, origin="news", verified=False,
                           url=by_short[u.item_id].url)
            for u in out.upcoming if u.item_id in by_short]


def _carried(t: TheatreV2, previous: TheatreV2 | None, now: datetime, keep_hours: float) -> None:
    if previous and previous.written_at and now - previous.written_at <= timedelta(
            hours=keep_hours):
        t.lines, t.top_items = previous.lines, previous.top_items
        t.sk_angle_en, t.sk_angle_sk = previous.sk_angle_en, previous.sk_angle_sk
        t.written_at, t.written_by = previous.written_at, previous.written_by


def watchlist(config_dir: Path, found: list[WatchlistEntry], previous: list[WatchlistEntry],
              now: datetime) -> list[WatchlistEntry]:
    """Hand-entered dates (verified), then dates from the news (unverified): this run's and
    earlier ones still ahead. Future only; a day that has a hand-entered date takes no other."""
    today = now.date()
    manual = [e for e in old.watchlist(config_dir / "watchlist.yaml", None, set(), now)]
    days = {e.date for e in manual}
    news: dict[tuple, WatchlistEntry] = {}
    for e in [*found, *(p for p in previous if p.origin == "news")]:
        if e.date >= today and e.date not in days:
            news.setdefault((e.date, e.title_en), e)
    return sorted([*manual, *news.values()], key=lambda e: e.date)[:MAX_WATCHLIST]


def brief(articles: dict[str, Article], previous: GeopoliticsFile | None, baselines: dict,
          ai, write: bool, now: datetime, cfg: dict, cfg_score: dict, config_dir: Path,
          ) -> tuple[GeopoliticsFile, dict]:
    """The geopolitics file and what happened: theatres written, carried, failed, and those
    left with text older than this run although they had reports (stale). write is False
    outside the scoring hours: activity is refreshed and the text is carried."""
    specs = yaml.safe_load((config_dir / "theatres.yaml").read_text())["theatres"]
    countries = old.theatre_countries(config_dir)
    before = {t.id: t for t in previous.theatres} if previous else {}
    stats = {"written": [], "carried": [], "failed": {}, "stale": []}
    theatres, found = [], []
    for spec in specs:
        act, spark = old.activity(baselines, spec["activity"], now, cfg_score)
        t = TheatreV2(id=spec["id"], name_en=spec["name_en"], name_sk=spec["name_sk"],
                      activity=act, countries=countries[spec["id"]],
                      tone=old.tone(baselines, spec["activity"], now, cfg_score), sparkline=spark)
        reports = theatre_reports(articles, countries[t.id], cfg["theatres"][t.id], now, cfg)
        by_short = {str(n): a for n, a in enumerate(reports, 1)}
        if write and ai is not None and reports:
            earlier = [line.text_en for line in before[t.id].lines] if t.id in before else []
            try:
                out, model = ai.ask(
                    "brief", BRIEF_SYSTEM,
                    brief_user(t.name_en, now.date().isoformat(),
                               [_row(s, a) for s, a in by_short.items()], earlier),
                    BRIEF_SCHEMA, "brief", parse_brief)
                found += _written(t, out, by_short, ai.models[model].model, now)
                stats["written"].append(t.id)
            except AiUnavailable as e:
                stats["failed"][t.id] = str(e)
                log.warning("no brief for %s: %s", t.id, e)
        if t.written_at is None:
            _carried(t, before.get(t.id), now, cfg["keep_hours"])
            if t.written_at:
                stats["carried"].append(t.id)
        if write and reports and t.written_at != now:
            stats["stale"].append(t.id)
        theatres.append(t)
    # A report can belong to several theatres (a loan to Ukraine is Russia and Ukraine, Slovak
    # policy and EU defence at once), and each wrote its own line about it: on 2026-11-12 the
    # brief said the same thing three times. A development is told once, by the first theatre.
    told: set[str] = set()
    for t in theatres:
        fresh = [line for line in t.lines if not set(line.item_ids) <= told]
        told |= {i for line in t.lines for i in line.item_ids}
        t.lines = fresh
    log.info("brief: %s", stats)
    return GeopoliticsFile(
        schema_version=2, updated_at=now, theatres=theatres,
        watchlist=watchlist(config_dir, found, previous.watchlist if previous else [], now),
    ), stats
