"""Made-up sample data for developing the frontend before scoring exists.

python -m pipeline.tools.sample_data OUT_DIR   writes latest.json and timeseries.json

Every file has sample: true and every title starts with [Sample] / [Ukážka]; the site
shows a banner on every page when it renders sample data. The numbers are invented and
mean nothing. Built through the pydantic models, so the sample always matches the schema.
"""

import json
import math
import random
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml

from ..models import (
    SCHEMA_VERSION,
    AcledActivity,
    Activity,
    AnchorReading,
    Brief,
    BriefLine,
    Classification,
    Component,
    Diff,
    Driver,
    Event,
    Gate,
    Geopolitics,
    Item,
    LlmAssessment,
    OfficialLevel,
    Place,
    RegionAssessment,
    Run,
    RunCounts,
    RunInfo,
    SourceHealth,
    Terrorism,
    Theatre,
    Timeseries,
    TimeseriesRow,
    Tone,
    TopItem,
    ValueChange,
    WatchlistEntry,
)
from ..score.geopolitics import theatre_countries

NOW = datetime(2026, 10, 22, 13, 9, tzinfo=UTC)
CONFIG = Path(__file__).parents[1] / "config"


def en(t: str) -> str:
    return f"[Sample] {t}"


def sk(t: str) -> str:
    return f"[Ukážka] {t}"


# (id, title_en, title_sk, type, ideology, severity, days_ago, country, place, lat, lon,
#  sk_link, domains, tier_a)
EVENTS = [
    ("evt_s1", "Police detain man suspected of planning an attack in Bratislava",
     "Polícia zadržala muža podozrivého z plánovania útoku v Bratislave",
     "plot_disrupted", "right_wing", 1, 2, "SK", "Bratislava", 48.148, 17.107, "direct",
     ["teraz.sk", "sme.sk", "minv.sk"], True),
    ("evt_s2", "Knife attack at a Vienna railway station, two injured",
     "Útok nožom na železničnej stanici vo Viedni, dvaja zranení",
     "attack", "jihadist", 3, 5, "AT", "Vienna", 48.208, 16.373, "indirect",
     ["orf.at", "derstandard.at"], False),
    ("evt_s3", "Arson attack on a rail signal box in eastern Poland attributed to a foreign state",
     "Podpaľačský útok na železničné návestidlo vo východnom Poľsku pripisovaný cudziemu štátu",
     "sabotage", "state_linked", 2, 9, "PL", "Lublin", 51.246, 22.568, "indirect",
     ["pap.pl", "dw.com"], False),
    ("evt_s4", "Europol-supported operation arrests 9 over online jihadist propaganda",
     "Operácia s podporou Europolu: 9 zatknutých za online džihádistickú propagandu",
     "arrest", "jihadist", 1, 12, "BE", "Brussels", 50.850, 4.352, "none",
     ["europol.europa.eu"], True),
    ("evt_s5", "Vehicle ramming in a French city centre, one dead",
     "Vrazenie autom do ľudí v centre francúzskeho mesta, jeden mŕtvy",
     "attack", "unknown", 4, 16, "FR", "Lyon", 45.764, 4.836, "none",
     ["france24.com", "bbc.co.uk"], False),
    ("evt_s6", "Czech court convicts teenager of preparing a school attack",
     "Český súd odsúdil tínedžera za prípravu útoku na školu",
     "conviction", "right_wing", 1, 20, "CZ", "Brno", 49.195, 16.607, "indirect",
     ["ct24.ceskatelevize.cz"], False),
    ("evt_s7", "Threat statement against Slovak officials posted on an extremist channel",
     "Vyhrážky slovenským predstaviteľom zverejnené na extrémistickom kanáli",
     "threat_statement", "other", 0, 24, "SK", "Slovakia", 48.669, 19.699, "direct",
     ["aktuality.sk"], False),
    ("evt_s8", "Failed explosive device found near a Hungarian government building",
     "Nefunkčné výbušné zariadenie nájdené pri maďarskej vládnej budove",
     "attempted_attack", "unknown", 2, 27, "HU", "Budapest", 47.497, 19.040, "indirect",
     ["telex.hu", "index.hu"], False),
]

# Geopolitics reports with a place, for the map: (title_en, domain, country, place, lat, lon)
GEO_ITEMS = [
    ("Drone strikes hit energy sites near Kharkiv", "geopolitics", "UA", "Kharkiv", 49.993,
     36.231),
    ("EU foreign ministers agree a new sanctions package in Brussels", "geopolitics", "BE",
     "Brussels", 50.850, 4.352),
    ("Slovak defence minister meets NATO counterparts in Bratislava", "geopolitics", "SK",
     "Bratislava", 48.148, 17.107),
    ("Cyber attack disrupts a Czech hospital network", "cyber", "CZ", "Prague", 50.088, 14.421),
    ("Protests in Belgrade over election results", "unrest", "RS", "Belgrade", 44.787, 20.457),
    ("Strikes reported in southern Lebanon", "geopolitics", "LB", "Tyre", 33.271, 35.196),
]

THEATRES = [
    ("russia_ukraine", "Russia and Ukraine war", "Vojna Ruska proti Ukrajine",
     0.58, 1.6, 412, 380.0),
    ("hybrid_eu", "Hybrid threats to the EU", "Hybridné hrozby voči EÚ", 0.49, 1.2, None, None),
    ("sk_policy", "Slovak foreign and security policy",
     "Zahraničná a bezpečnostná politika SR", 0.33, 0.85, None, None),
    ("eu_defence", "EU policy and defence", "Politika a obrana EÚ", 0.41, 1.1, None, None),
    ("middle_east", "Middle East", "Blízky východ", 0.66, 2.3, 288, 301.5),
    ("western_balkans", "Western Balkans", "Západný Balkán", 0.22, 0.55, 14, 19.25),
]


def _sources() -> list[SourceHealth]:
    sources = yaml.safe_load((CONFIG / "sources.yaml").read_text())["sources"]
    out = []
    for i, s in enumerate(sources):
        failed = i == 1  # show what a failing source looks like
        out.append(SourceHealth(
            id=s["id"], name=s["name"], tier=s["tier"], group=s["group"],
            status="failed" if failed else ("ok" if s["enabled"] else "disabled"),
            last_success=NOW - timedelta(hours=11 if failed else 0),
            last_error=NOW if failed else None, items=0 if failed else 12 + i,
            http_status=503 if failed else 200, error="HTTP 503 (sample)" if failed else None,
            note=None))
    return out


def _events_and_items() -> tuple[list[Event], list[Item]]:
    events, items = [], []
    for (eid, t_en, t_sk, etype, ideo, sev, ago, cc, place, lat, lon, link, domains,
         tier_a) in EVENTS:
        when = NOW - timedelta(days=ago, hours=3)
        p = Place(name=place, lat=lat, lon=lon, precision="country" if place == "Slovakia"
                  else "city")
        item_ids = []
        for n, dom in enumerate(domains):
            iid = f"{eid}_i{n}"
            item_ids.append(iid)
            items.append(Item(
                id=iid, source_id="europol" if dom == "europol.europa.eu" else "tasr",
                tier="A" if dom in ("europol.europa.eu", "minv.sk") else "B",
                url="", title=en(t_en), lang="en",  # no address: sample items are not clickable
                published_at=when + timedelta(hours=n), fetched_at=when + timedelta(hours=n + 1),
                snippet="Sample item for frontend development. Not real.", domain=dom,
                classification=Classification(
                    status="llm", relevant=True, domain="terrorism" if ideo != "state_linked"
                    else "hybrid", event_type=etype, ideology=ideo, severity=sev, sk_link=link,
                    countries=[cc], places=[p], event_key=eid, summary_en=en(t_en),
                    summary_sk=sk(t_sk), confidence=0.8),
                event_id=eid))
        events.append(Event(
            id=eid, title_en=en(t_en), title_sk=sk(t_sk), event_type=etype, ideology=ideo,
            severity=sev, date=when.date(), country=cc, place=p, sk_link=link,
            item_ids=item_ids, domains=domains, has_tier_a=tier_a,
            corroborated=tier_a or len(domains) >= 2, first_seen=when, last_updated=NOW))
    for n, (t_en, dom, cc, place, lat, lon) in enumerate(GEO_ITEMS):
        when = NOW - timedelta(hours=2 + n)
        items.append(Item(
            id=f"geo_s{n}", source_id="tasr", tier="B", url="", title=en(t_en), lang="en",
            published_at=when, fetched_at=when + timedelta(minutes=30),
            snippet="Sample item for frontend development. Not real.", domain="tasr.sk",
            classification=Classification(
                status="llm", relevant=True, domain=dom, event_type="other",
                ideology="unknown", severity=0, sk_link="none", countries=[cc],
                places=[Place(name=place, lat=lat, lon=lon, precision="city")],
                summary_en=en(t_en), confidence=0.8)))
    return events, items


def _anchors() -> list[AnchorReading]:
    def a(id_, cc, name, url, scale, raw, since=None, status="ok"):
        lvl = scale.index(raw) + 1
        return AnchorReading(id=id_, country=cc, name=name, url=url, scale=scale, raw=raw,
                             level=lvl, normalized=round((lvl - 1) / (len(scale) - 1), 3),
                             since=since, as_of=NOW, status=status)
    return [
        a("anchor_sk_sis", "SK", "SIS NBAC", "https://www.sis.gov.sk/o-nas/nbac-sto.html",
          ["1", "2", "3", "4"], "2", date(2017, 8, 23)),
        a("anchor_fr_vigipirate", "FR", "Vigipirate", "https://www.sgdsn.gouv.fr/vigipirate",
          ["vigilance", "vigilance renforcée", "alerte attentat"], "vigilance renforcée",
          date(2026, 6, 22)),
        a("anchor_be_ocam", "BE", "OCAM/CUTA", "https://ocam.belgium.be/",
          ["faible", "moyen", "grave", "tresGrave"], "grave"),
        a("anchor_nl_nctv", "NL", "NCTV", "https://www.nctv.nl/",
          ["minimaal", "beperkt", "aanzienlijk", "substantieel", "kritiek"], "substantieel",
          date(2023, 12, 12)),
        a("anchor_pl_mswia", "PL", "Stopnie alarmowe (MSWiA)", "https://www.gov.pl/web/mswia",
          ["ALFA", "BRAVO", "CHARLIE", "DELTA"], "BRAVO"),
    ] + [
        a(f"anchor_fcdo_{cc.lower()}", cc, "FCDO travel advice",
          "https://www.gov.uk/foreign-travel-advice",
          ["cannot be ruled out", "likely", "very likely"], raw)
        for cc, raw in (("SK", "cannot be ruled out"), ("FR", "very likely"), ("DE", "very likely"),
                        ("BE", "likely"), ("AT", "likely"), ("PL", "cannot be ruled out"))
    ]


def _region(region: str, index: int, prev: int, events: list[Event]) -> RegionAssessment:
    ids = [e.id for e in events if region == "EU" or e.sk_link != "none"]
    comps = [
        Component(id="events", weight=0.35, value=0.41 if region == "SK" else 0.52,
                  inputs={"weighted_sum": 3.8 if region == "SK" else 21.4,
                          "baseline_median": 2.9 if region == "SK" else 14.0,
                          "floor": 1.0 if region == "SK" else 4.0}, event_ids=ids[:5]),
        Component(id="media", weight=0.15, value=0.33 if region == "SK" else 0.45,
                  inputs={"articles_24h": 41 if region == "SK" else 1210,
                          "baseline_median": 47.0 if region == "SK" else 1050.0}),
        Component(id="anchors", weight=0.20, value=0.30 if region == "SK" else 0.58,
                  inputs={"anchors_used": 2 if region == "SK" else 5, "rose_30d": 0}),
        Component(id="llm", weight=0.30, value=0.375 if region == "SK" else 0.46,
                  inputs={"level": 2, "position": "mid" if region == "SK" else "high"}),
    ]
    gates = [Gate(id="floor_eu_attack_30d", effect="min_level 2",
                  event_ids=[e.id for e in events if e.event_type == "attack"])]
    if region == "SK":
        gates.append(Gate(id="cap_sk_2", effect="max_level 2", event_ids=[]))
    return RegionAssessment(
        region=region, level=2, index=index, index_prev=prev, level_prev=2, rules_level=2,
        components=comps, gates=gates,
        llm=LlmAssessment(
            status="ok", level=2, position="mid" if region == "SK" else "high",
            confidence="medium", model="sample",
            drivers=[
                Driver(text_en=en("A disrupted plot in Bratislava keeps a direct Slovak link "
                                  "in the last 30 days."),
                       text_sk=sk("Prekazený plán útoku v Bratislave znamená priame prepojenie "
                                  "na Slovensko za posledných 30 dní."), event_ids=["evt_s1"]),
                Driver(text_en=en("An attack in Vienna raises proximity pressure."),
                       text_sk=sk("Útok vo Viedni zvyšuje tlak z blízkosti."),
                       event_ids=["evt_s2"]),
            ],
            what_changed_en=en("The index rose by 3 points after the Bratislava arrest; the "
                               "level is unchanged."),
            what_changed_sk=sk("Index stúpol o 3 body po zadržaní v Bratislave; úroveň sa "
                               "nezmenila.")),
        disagreement=False,
        official=OfficialLevel(source="SIS NBAC", level=2, label_sk="zvýšený stupeň ohrozenia",
                               since=date(2017, 8, 23), checked_at=NOW,
                               url="https://www.sis.gov.sk/o-nas/nbac-sto.html")
        if region == "SK" else None,
        anchor_ids=["anchor_sk_sis", "anchor_fcdo_sk"] if region == "SK"
        else ["anchor_fr_vigipirate", "anchor_be_ocam", "anchor_nl_nctv", "anchor_pl_mswia"])


def _geopolitics(items: list[Item]) -> Geopolitics:
    rnd = random.Random(7)
    countries = theatre_countries(CONFIG)
    theatres = []
    for tid, n_en, n_sk, value, ratio, acled7, acled_avg in THEATRES:
        wave = [value + 0.12 * math.sin(d / 4) + rnd.uniform(-.06, .06) for d in range(30)]
        spark = [round(max(0.05, min(0.95, w)), 3) for w in wave]
        theatres.append(Theatre(
            id=tid, name_en=n_en, name_sk=n_sk, countries=countries[tid],
            activity=Activity(value=value, articles_24h=int(300 * ratio),
                              baseline_median=300.0),
            acled=AcledActivity(events_7d=acled7, avg_week_prev_4=acled_avg)
            if acled7 is not None else None,
            tone=Tone(value=-4.1 - ratio, baseline_median=-3.9), sparkline=spark,
            top_items=[TopItem(item_id=items[i].id, summary_en=en(f"Development {i + 1} in "
                                                                   f"{n_en}."),
                               summary_sk=sk(f"Vývoj {i + 1}: {n_sk}."))
                       for i in range(3)],
            sk_angle_en=en("Slovak ministers commented on the issue.") if tid in
            ("russia_ukraine", "sk_policy") else None,
            sk_angle_sk=sk("Slovenskí ministri sa k téme vyjadrili.") if tid in
            ("russia_ukraine", "sk_policy") else None))
    brief = Brief(status="ok", lines=[
        BriefLine(text_en=en(f"Brief line {i + 1} about the most relevant development."),
                  text_sk=sk(f"Riadok prehľadu {i + 1} o najdôležitejšom vývoji."),
                  item_ids=[items[i].id]) for i in range(6)],
        what_changed_en=en("Activity in the Middle East rose above twice its normal level."),
        what_changed_sk=sk("Aktivita na Blízkom východe stúpla nad dvojnásobok bežnej úrovne."))
    watch = [
        WatchlistEntry(date=date(2026, 10, 23), title_en=en("European Council meeting"),
                       title_sk=sk("Zasadnutie Európskej rady"), origin="manual", verified=True),
        WatchlistEntry(date=date(2026, 10, 29), title_en=en("NATO defence ministers meet"),
                       title_sk=sk("Stretnutie ministrov obrany NATO"), origin="news",
                       verified=False),
    ]
    return Geopolitics(theatres=theatres, brief=brief, watchlist=watch)


def build() -> tuple[Run, Timeseries]:
    events, items = _events_and_items()
    run = Run(
        schema_version=SCHEMA_VERSION,
        run=RunInfo(id="2026-10-22T13", status="partial", started_at=NOW - timedelta(minutes=4),
                    finished_at=NOW, window_start=NOW - timedelta(hours=11), git_sha=None,
                    counts=RunCounts(fetched=2140, from_buffer=310, after_dedupe=1310,
                                     in_window=len(items))),
        sources=_sources(), items=items, anchors=_anchors(),
        terrorism=Terrorism(SK=_region("SK", 37, 34, events), EU=_region("EU", 49, 50, events)),
        geopolitics=_geopolitics(items), events=events,
        diff=Diff(new_event_ids=["evt_s1"], level_changes=[],
                  anchor_changes=[ValueChange(id="anchor_be_ocam", value_from="2",
                                              value_to="3")],
                  source_changes=[ValueChange(id="tasr", value_from="ok", value_to="failed")]),
        sample=True)
    rows = []
    rnd = random.Random(3)
    for n in range(180 * 2):
        at = NOW - timedelta(hours=12 * (180 * 2 - 1 - n))
        for region, base in (("SK", 36), ("EU", 47)):
            idx = round(base + 6 * math.sin(n / 23) + rnd.uniform(-3, 3)
                        + (9 if region == "EU" and 200 < n < 214 else 0))
            rows.append(TimeseriesRow(
                run_id=at.strftime("%Y-%m-%dT%H"), at=at, region=region, index=idx,
                level=3 if idx >= 50 and region == "EU" and 200 < n < 214 else 2,
                rules_level=2, llm_level=2,
                components={"events": round(idx / 100 + .03, 3), "media": round(idx / 100, 3),
                            "anchors": .3 if region == "SK" else .58, "llm": .375}))
    return run, Timeseries(schema_version=1, rows=rows, sample=True)


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    run, ts = build()
    for name, model in (("latest.json", run), ("timeseries.json", ts)):
        (out / name).write_text(json.dumps(model.model_dump(mode="json"), ensure_ascii=False,
                                           separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
