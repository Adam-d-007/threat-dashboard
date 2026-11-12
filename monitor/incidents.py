"""Stage 3, incidents: an incident is a thing that happened; articles are reports about it.

A labelled report about an incident (a new one, or an update to an earlier one) is shown to a
model with the recent incidents, and the model must answer with one of their ids or "new".
A matched report joins that incident's timeline; "new" makes an incident from the facts the
report states. Commentary never gets here, and a report no model has matched yet makes nothing.

When one answer says "new" more than once, only the first makes an incident at once; the others
are asked again with that incident on the list, since they may be about it.
"""

import hashlib
import logging
from datetime import date, datetime, timedelta

from pipeline.models import Event

from .ai.client import AiUnavailable
from .ai.labels import INCIDENT_KINDS
from .ai.tasks import MATCH_SYSTEM, NEW, match_schema, match_user, parse_matches
from .models import Article, Correction, Incident, Report

log = logging.getLogger("monitor.incidents")

REMOVED = "removed"
SK_RANK = {"none": 0, "indirect": 1, "direct": 2}
TIER_RANK = {"A": 0, "B": 1, "C": 2}
UPDATED_DAYS = 14   # an older incident still in the news is offered to the matcher as well


def incident_id(article_id: str) -> str:
    return "inc_" + hashlib.sha1(article_id.encode()).hexdigest()[:12]


def needs_match(a: Article, cfg: dict) -> bool:
    lab = a.label
    return bool(lab and lab.kind in INCIDENT_KINDS and lab.domain in cfg["domains"]
                and lab.incident_country and a.incident_id is None
                and a.match_attempts < cfg["max_attempts"])


def event_date(a: Article) -> date:
    """The day the report says it happened; the day of the report when it does not say, or
    names a day after the report."""
    published = a.published_at.date()
    stated = date.fromisoformat(a.label.incident_date) if a.label.incident_date else published
    return stated if stated <= published + timedelta(days=1) else published


def report_of(a: Article) -> Report:
    lab = a.label
    return Report(article_id=a.id, url=a.url, source=a.domain, tier=a.tier,
                  published_at=a.published_at, kind=lab.kind, summary_en=lab.summary_en,
                  summary_sk=lab.summary_sk, type=lab.incident_type, severity=lab.severity,
                  event_date=event_date(a), also_reported_by=a.also_reported_by)


def recompute(inc: Incident) -> None:
    """Everything an incident derives from its timeline. Severity is the highest any report
    states (a death toll that rises is picked up) and the type comes with it. The date and the
    title come from the first report of the incident itself, or the first update if it is only
    known through updates."""
    inc.reports.sort(key=lambda r: r.published_at)
    first = next((r for r in inc.reports if r.kind == "new_incident"), inc.reports[0])
    worst = max(inc.reports, key=lambda r: (r.severity, r.kind == "new_incident"))
    inc.severity, inc.type = worst.severity, worst.type
    inc.date = first.event_date
    if first.summary_en:
        inc.title_en, inc.title_sk = first.summary_en, first.summary_sk
    inc.domains = list(dict.fromkeys(d for r in inc.reports
                                     for d in [r.source, *r.also_reported_by] if d))
    inc.has_tier_a = any(r.tier == "A" for r in inc.reports)
    inc.best_tier = min((r.tier for r in inc.reports), key=TIER_RANK.get)
    inc.corroborated = inc.has_tier_a or len(inc.domains) >= 2


def new_incident(a: Article, now: datetime) -> Incident:
    lab = a.label
    inc = Incident(
        id=incident_id(a.id), type=lab.incident_type, severity=lab.severity, date=event_date(a),
        country=lab.incident_country, place=a.place, ideology=lab.ideology, sk_link=lab.sk_link,
        topic=lab.domain, title_en=lab.summary_en, title_sk=lab.summary_sk,
        reports=[report_of(a)], domains=[], has_tier_a=False, best_tier=None,
        corroborated=False, first_seen=now, last_updated=now)
    recompute(inc)
    return inc


def add_report(inc: Incident, a: Article, now: datetime) -> None:
    lab = a.label
    if all(r.article_id != a.id for r in inc.reports):
        inc.reports.append(report_of(a))
    if lab.domain == "terrorism":
        inc.topic = "terrorism"
    if inc.ideology == "unknown":
        inc.ideology = lab.ideology
    if SK_RANK[lab.sk_link] > SK_RANK[inc.sk_link]:
        inc.sk_link = lab.sk_link
    if a.place and (inc.place is None or (inc.place.precision != "city"
                                          and a.place.precision == "city")):
        inc.place = a.place
    inc.last_updated = now
    recompute(inc)


def candidates(incidents: list[Incident], now: datetime, cfg: dict) -> list[Incident]:
    """Incidents a new report could be about: recent ones, and older ones still in the news."""
    recent = (now - timedelta(days=cfg["candidate_days"])).date()
    active = now - timedelta(days=UPDATED_DAYS)
    live = [i for i in incidents if i.date >= recent or i.last_updated >= active]
    return sorted(live, key=lambda i: i.date, reverse=True)[:cfg["max_candidates"]]


def _incident_row(i: Incident) -> dict:
    return {"id": i.id, "date": i.date.isoformat(), "country": i.country,
            "place": i.place.name if i.place else None, "type": i.type, "summary": i.title_en}


def _report_row(short: str, a: Article) -> dict:
    lab = a.label
    return {"id": short, "published": a.published_at.date().isoformat(), "kind": lab.kind,
            "type": lab.incident_type, "date": lab.incident_date,
            "country": lab.incident_country, "place": lab.incident_place,
            "summary": lab.summary_en}


def match(articles: dict[str, Article], incidents: list[Incident], ai, cfg: dict,
          now: datetime) -> dict:
    """Put each waiting report on an incident's timeline, or make its incident. Returns counts
    and, when it stopped early, why."""
    queue = sorted((a for a in articles.values() if needs_match(a, cfg)),
                   key=lambda a: a.published_at)
    stats = {"attached": 0, "new": 0, "unanswered": 0, "stopped": None}
    deadline = ai.clock() + cfg["max_seconds"]
    while queue:
        batch, queue = queue[:cfg["batch_size"]], queue[cfg["batch_size"]:]
        by_short = {f"r{n}": a for n, a in enumerate(batch, 1)}
        offered = candidates(incidents, now, cfg)
        by_id = {i.id: i for i in offered}
        try:
            answers, model = ai.ask(
                "match", MATCH_SYSTEM,
                match_user([_incident_row(i) for i in offered],
                           [_report_row(s, a) for s, a in by_short.items()]),
                match_schema(list(by_id)), "matches",
                lambda t, r=set(by_short), i=set(by_id): parse_matches(t, r, i), deadline)
        except AiUnavailable as e:
            stats["stopped"] = str(e)
            log.warning("matching stopped: %s", e)
            break
        created, again = False, []
        for short, a in by_short.items():
            answer = answers.get(short)
            if answer is None:
                a.match_attempts += 1
                stats["unanswered"] += 1
                continue
            if answer == NEW and created:
                again.append(a)
                continue
            if answer == NEW:
                inc = new_incident(a, now)
                incidents.append(inc)
                created = True
                stats["new"] += 1
            else:
                inc = by_id[answer]
                add_report(inc, a, now)
                stats["attached"] += 1
            a.incident_id, a.matched_by = inc.id, model
        queue = again + queue
    stats["waiting"] = sum(1 for a in articles.values() if needs_match(a, cfg))
    log.info("matching: %s", stats)
    return stats


def prune(incidents: list[Incident], now: datetime, keep_days: int) -> list[Incident]:
    oldest = (now - timedelta(days=keep_days)).date()
    return [i for i in incidents if i.date >= oldest]


def seed(events: list[Event], removed: list[str], now: datetime, keep_days: int,
         item_id) -> list[Incident]:
    """The old pipeline's events carried over as incidents, once, at the first run. Only real
    incidents come along (severity 1 or more); its severity 0 "events" were follow-ups and
    commentary. item_id maps a URL to an article id, as the old pipeline made them."""
    oldest = (now - timedelta(days=keep_days)).date()
    out = []
    for e in events:
        iid = "inc_" + e.id.removeprefix("evt_")
        if e.severity < 1 or e.date < oldest or iid in removed or e.topic == "unrest":
            continue
        tier = "A" if e.has_tier_a else (e.best_tier or "B")
        urls = e.urls or [f"urn:event:{e.id}"]
        reports = [Report(
            article_id=item_id(u), url=u, source=e.domains[n] if n < len(e.domains) else "",
            tier=tier, published_at=e.first_seen, kind="new_incident" if n == 0 else "update",
            summary_en=e.title_en if n == 0 else None, summary_sk=e.title_sk if n == 0 else None,
            type=e.event_type, severity=e.severity, event_date=e.date,
            also_reported_by=e.domains if n == 0 else []) for n, u in enumerate(urls)]
        inc = Incident(
            id=iid, type=e.event_type, severity=e.severity, date=e.date, country=e.country,
            place=e.place, ideology=e.ideology, sk_link=e.sk_link,
            topic="hybrid" if e.topic == "hybrid" else "terrorism", title_en=e.title_en,
            title_sk=e.title_sk, reports=reports, domains=[], has_tier_a=False, best_tier=None,
            corroborated=False, first_seen=e.first_seen, last_updated=e.last_updated,
            seeded_from=e.id)
        recompute(inc)
        out.append(inc)
    return out


def to_event(i: Incident) -> Event:
    """An incident in the shape the scoring formulas take."""
    return Event(
        id=i.id, title_en=i.title_en, title_sk=i.title_sk, event_type=i.type,
        ideology=i.ideology, severity=i.severity, date=i.date, country=i.country, place=i.place,
        sk_link=i.sk_link, topic=i.topic, item_ids=[r.article_id for r in i.reports],
        urls=[r.url for r in i.reports], domains=i.domains, has_tier_a=i.has_tier_a,
        best_tier=i.best_tier, corroborated=i.corroborated, first_seen=i.first_seen,
        last_updated=i.last_updated)


def apply_overrides(incidents: list[Incident], articles: dict[str, Article], overrides: dict,
                    removed: list[str], now: datetime) -> list[Correction]:
    """Adam's corrections (monitor/overrides.yaml), applied every run; each is safe to apply
    again. Changes incidents and removed in place."""
    by_id = {i.id: i for i in incidents}
    done = []

    def drop(iid: str) -> None:
        incidents.remove(by_id.pop(iid))

    for m in overrides.get("merge") or []:
        into, gone = by_id.get(m["into"]), by_id.get(m["from"])
        if into and gone:
            known = {r.article_id for r in into.reports}
            into.reports.extend(r for r in gone.reports if r.article_id not in known)
            into.last_updated = now
            recompute(into)
            drop(gone.id)
            for a in articles.values():
                if a.incident_id == gone.id:
                    a.incident_id = into.id
        done.append(Correction(action="merge", note=m["note"],
                               applied=bool(into) and m["from"] not in by_id))
    for r in overrides.get("remove") or []:
        if r["id"] in by_id:
            drop(r["id"])
        if r["id"] not in removed:
            removed.append(r["id"])
        for a in articles.values():
            if a.incident_id == r["id"]:
                a.incident_id = REMOVED
        done.append(Correction(action="remove", note=r["note"], applied=True))
    for d in overrides.get("detach") or []:
        owner = next((i for i in incidents if any(r.url == d["url"] for r in i.reports)), None)
        report = next((r for r in owner.reports if r.url == d["url"]), None) if owner else None
        new_id = incident_id(report.article_id) if report else None
        if report and owner.id != new_id:
            owner.reports.remove(report)
            if owner.reports:
                recompute(owner)
            else:
                drop(owner.id)
            alone = owner.model_copy(deep=True, update={
                "id": new_id, "reports": [report.model_copy(update={"kind": "new_incident"})],
                "first_seen": now, "last_updated": now, "seeded_from": None})
            recompute(alone)
            incidents.append(alone)
            by_id[new_id] = alone
            if report.article_id in articles:
                articles[report.article_id].incident_id = new_id
        done.append(Correction(action="detach", note=d["note"], applied=report is not None))
    return done
