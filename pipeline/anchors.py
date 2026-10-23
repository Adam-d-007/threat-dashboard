"""Official threat levels (anchors) read from government pages, and other governments'
travel advice (UK FCDO wording and the sources under `travel` in anchors.yaml).

Each parser returns the raw value exactly as the page shows it; a value outside the
configured scale, zero matches or several matches raise, so a layout change fails loudly
instead of reporting a wrong level. A failed read keeps the last known value with its date.
"""

import hashlib
import html as htmllib
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

from .adapters.base import FetchError, get
from .adapters.dates import parse_local_date
from .models import AnchorReading

CONFIG = Path(__file__).parent / "config"
# A hand-entered level older than this is shown as stale until someone checks it again.
MANUAL_MAX_AGE_DAYS = 180
log = logging.getLogger("pipeline.anchors")


class AnchorError(Exception):
    pass


def _space(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _one(matches: list, what: str):
    if len(matches) != 1:
        raise AnchorError(f"expected exactly one {what}, found {len(matches)}")
    return matches[0]


def parse_sis(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    col = soup.select_one("div.main-column")
    if col is None:
        raise AnchorError("div.main-column not found")
    paras = [_space(p.get_text(" ")) for p in col.select("p")]
    para = _one([p for p in paras if "platí" in p and "stupeň teroristického ohrozenia" in p],
                "paragraph stating the current level")
    m = re.search(r"platí\s+(\d)\.\s*stupeň teroristického ohrozenia, ktorý bol vyhlásený dňa\s+"
                  r"(\d{1,2}\.\s*[^\W\d_]+\s+\d{4})", para)
    if not m:
        raise AnchorError(f"level sentence not recognised: {para[:160]!r}")
    return {"raw": m.group(1), "since": parse_local_date(m.group(2)),
            "text_hash": hashlib.sha1(para.encode()).hexdigest()}


def parse_ocam(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    shown = [d for d in soup.select("div.menace-item")
             if "display:block" in (d.get("style") or "").replace(" ", "")]
    return {"raw": _one(shown, "visible div.menace-item").get("data-menace-key")}


def parse_nctv(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    heads = [_space(h.get_text(" ")) for h in soup.find_all("h2")]
    head = _one([h for h in heads if h.startswith("Actueel dreigingsniveau:")],
                "'Actueel dreigingsniveau:' heading")
    raw = re.match(r"Actueel dreigingsniveau:\s*(\w+)", head).group(1)
    since = None
    if cap := soup.find("caption", string=re.compile(r"Sinds")):
        since = parse_local_date(_space(cap.get_text(" ")))
    return {"raw": raw, "since": since}


_PL_LEVEL = re.compile(r"(PIERWSZY|DRUGI|TRZECI|CZWARTY) STOPIEŃ ALARMOWY( CRP)? \(([A-Z-]+)\)")


def parse_mswia(html: str, today: date) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    box = _one(soup.select("div.editor-content div.alert.alert-danger"), "alert box")
    sentences = [_space(p.get_text(" ")) for p in box.select("p")]
    national = _one([s for s in sentences if "pozostałym terytorium" in s and _PL_LEVEL.search(s)],
                    "sentence for the rest of the territory")
    raw = _PL_LEVEL.search(national).group(3)
    others = [s for s in sentences if s != national and _PL_LEVEL.search(s)
              and re.search(r"[ąęłńóśźż]", s)]  # the Polish sentences, not their English copies
    exp = re.search(r"do (\d{1,2} [^\W\d_]+ \d{4}) r\.", national)
    expiry = parse_local_date(exp.group(1)) if exp else None
    expired = expiry is not None and expiry < today
    return {"raw": raw, "detail": " | ".join(others) or None,
            "stale_reason": f"the order behind this level expired on {expiry}" if expired else None}


_FCDO = [("very likely", re.compile(r"very likely")), ("likely", re.compile(r"\blikely\b")),
         ("cannot be ruled out", re.compile(r"cannot be ruled out"))]


def parse_fcdo(data: dict) -> dict:
    if data.get("document_type") != "travel_advice":
        raise AnchorError(f"document_type is {data.get('document_type')!r}, not travel_advice")
    part = _one([p for p in data["details"]["parts"] if p.get("slug") == "safety-and-security"],
                "safety-and-security part")
    soup = BeautifulSoup(part["body"], "html.parser")
    h3 = _one(soup.select('h3[id^="terrorism-in-"]'), "terrorism heading")
    p = h3.find_next("p")
    if p is None:
        raise AnchorError("no paragraph after the terrorism heading")
    sentence = _space(p.get_text(" "))
    for raw, rx in _FCDO:
        if rx.search(sentence):
            return {"raw": raw, "text_hash": hashlib.sha1(sentence.encode()).hexdigest()}
    raise AnchorError(f"terrorism sentence not recognised: {sentence!r}")


# --- Travel advice (anchors.yaml: travel). Each parser returns {ISO country: parsed}. -------

def _text(page: str) -> str:
    return _space(BeautifulSoup(page, "html.parser").get_text(" "))


def parse_us_state(xml: str, fips: dict[str, str]) -> dict[str, dict]:
    """State Department RSS: one item per country, with a 'Level N: ...' category and the
    country's FIPS code as another category (Slovakia is LO)."""
    out = {}
    for item in ET.fromstring(xml).iter("item"):
        cats = [c.text or "" for c in item.findall("category")]
        levels = [m.group(1) for c in cats if (m := re.match(r"Level ([1-4]):", c))]
        codes = [fips[c] for c in cats if c in fips]
        if len(levels) == 1 and len(codes) == 1:
            out[codes[0]] = {"raw": f"Level {levels[0]}",
                             "detail": _space(item.findtext("title") or ""),
                             "url": (item.findtext("link") or "").strip() or None}
    return out


_CA = ["normal precautions", "high degree of caution", "avoid non-essential travel",
       "avoid all travel"]


def parse_ca_gc(data: dict) -> dict[str, dict]:
    """advisory-state 0 to 3, named as on travel.gc.ca."""
    return {cc: {"raw": _CA[c["advisory-state"]], "detail": c["eng"]["advisory-text"],
                 "url": f"https://travel.gc.ca/destinations/{c['eng']['url-slug']}"
                 if c["eng"].get("url-slug") else None}
            for cc, c in data["data"].items()}


def parse_de_aa(data: dict) -> dict[str, dict]:
    """Auswärtiges Amt open data: warning flags per country. A situation-based warning counts
    as the warning of the same reach."""
    out = {}
    for v in data["response"].values():
        if not isinstance(v, dict) or "countryCode" not in v:
            continue
        raw = ("Reisewarnung" if v["warning"] or v["situationWarning"] else
               "Teilreisewarnung" if v["partialWarning"] or v["situationPartWarning"] else
               "keine Warnung")
        out[v["countryCode"]] = {"raw": raw}
    return out


_NZ = {"normal": "Level 1", "low": "Level 1", "medium": "Level 2", "high": "Level 3",
       "avoid": "Level 4"}


def parse_nz_safetravel(page: str) -> dict[str, dict]:
    """The destinations page embeds every country's adviceLevel. 'normal' means New Zealand
    issues no advisory; it counts as level 1 (checked on the Bulgaria and Slovakia pages)."""
    pairs = re.findall(r'"code":"([a-z]{2})","link":\{[^}]*?"href":"([^"]*)"[^}]*\},'
                       r'"region":"[^"]*","adviceLevel":"([^"]*)"', htmllib.unescape(page))
    if not pairs:
        raise AnchorError("no adviceLevel entries found")
    out = {}
    for code, href, level in pairs:
        if level not in _NZ:
            raise AnchorError(f"unknown adviceLevel {level!r}")
        out[code.upper()] = {"raw": _NZ[level],
                             "detail": "no advisory" if level == "normal" else None,
                             "url": f"https://www.safetravel.govt.nz{href}"
                             if href.startswith("/") else None}
    return out


def parse_nl_bz(data: dict) -> dict:
    m = re.search(r"kleurcode van het reisadvies voor .{1,60}? is (groen|geel|oranje|rood)",
                  _text(data["introduction"]))
    if not m:
        raise AnchorError("colour code sentence not found")
    return {"raw": m.group(1)}


def parse_jp_mofa(xml: str) -> dict:
    """Japan's open data: riskLevel1 to riskLevel4 are non-zero where that danger level is
    issued for some part of the country; 0 when no danger information is issued."""
    root = ET.fromstring(xml)
    issued = [n for n in (1, 2, 3, 4) if (root.findtext(f"riskLevel{n}") or "").strip() not in
              ("", "0")]
    if root.find("riskLevel1") is None:
        raise AnchorError("riskLevel fields missing")
    return {"raw": f"Level {max(issued)}" if issued else "no warning"}


def parse_cz_mzv(page: str) -> dict:
    """The 'Aktuální doporučení a varování' box: none, a notice, or a travel warning."""
    m = re.search(r"Aktuální doporučení a varování (.{0,600}?) Celní a devizové předpisy",
                  _text(page))
    if not m:
        raise AnchorError("current recommendations box not found")
    box = m.group(1)
    raw = ("žádné" if "Nebylo nalezeno žádné aktuální upozornění" in box else
           "varování" if "Varování" in box else "upozornění")
    return {"raw": raw, "detail": box[:200]}


_DK = ["Vær opmærksom", "Vær ekstra forsigtig", "Vi fraråder alle ikke-nødvendige rejser",
       "Vi fraråder alle rejser"]


def parse_dk_um(page: str) -> dict:
    text = _text(page)
    if re.search(r"Vi har ingen rejsevejledning for", text):
        return {"raw": "ingen rejsevejledning"}
    m = re.search(r"Gyldig: [\d.]+ (" + "|".join(map(re.escape, _DK)) + ")", text)
    if not m:
        raise AnchorError("travel guidance level not found")
    return {"raw": m.group(1)}


def _travel_parse(cfg: dict, r, fips: dict[str, str]) -> dict[str, dict]:
    parser = cfg["parser"]
    if parser == "us_state":
        return parse_us_state(r.text, fips)
    if parser == "ca_gc":
        return parse_ca_gc(r.json())
    if parser == "de_aa":
        return parse_de_aa(r.json())
    if parser == "nz_safetravel":
        return parse_nz_safetravel(r.text)
    single = {"nl_bz": lambda: parse_nl_bz(r.json()), "jp_mofa": lambda: parse_jp_mofa(r.text),
              "cz_mzv": lambda: parse_cz_mzv(r.text), "dk_um": lambda: parse_dk_um(r.text)}
    if parser not in single:
        raise AnchorError(f"unknown parser {parser!r}")
    return {cfg["countries"][0]: single[parser]()}


def read_travel(cfg: dict, eu: list[str], fips: dict[str, str], prev: dict, now: datetime,
                ) -> list[AnchorReading]:
    """One request for the source, then one reading per country it covers. A country the
    source does not list, or a failed request, keeps that country's last value."""
    # A government gives no travel advice for its own country (Germany for Germany).
    countries = [cc for cc in (eu if cfg["countries"] == "eu" else cfg["countries"])
                 if cc != cfg["issuer"]]
    cfgs = [{"id": f"anchor_{cfg['id']}_{cc.lower()}", "country": cc, "name": cfg["name"],
             "url": (cfg.get("pages") or {}).get(cc, cfg["page"]), "scale": cfg["scale"],
             "kind": "travel",
             "issuer": cfg["issuer"]} for cc in countries]
    try:
        parsed = _travel_parse(cfg, get(cfg["url"]), fips)
    except (AnchorError, FetchError, ValueError, KeyError, ET.ParseError,
            json.JSONDecodeError) as e:
        return [_failed(c, prev.get(c["id"]), f"{type(e).__name__}: {e}") for c in cfgs]
    out = []
    for c in cfgs:
        try:
            if c["country"] not in parsed:
                raise AnchorError(f"{c['country']} not in the source")
            out.append(_reading(c, now, parsed[c["country"]]))
        except AnchorError as e:
            out.append(_failed(c, prev.get(c["id"]), f"{type(e).__name__}: {e}"))
    return out


def _reading(cfg: dict, now: datetime, parsed: dict, manual: bool = False) -> AnchorReading:
    """parsed may carry as_of (when the value was last confirmed) and stale_reason."""
    raw = parsed["raw"]
    if raw not in cfg["scale"]:
        raise AnchorError(f"value {raw!r} is not on the scale {cfg['scale']}")
    level = cfg["scale"].index(raw) + 1
    return AnchorReading(
        id=cfg["id"], country=cfg["country"], name=cfg["name"],
        url=parsed.get("url") or cfg["url"], scale=cfg["scale"], raw=raw, level=level,
        normalized=round((level - 1) / (len(cfg["scale"]) - 1), 3), since=parsed.get("since"),
        as_of=parsed.get("as_of", now), status="stale" if parsed.get("stale_reason") else "ok",
        error=parsed.get("stale_reason"),
        text_hash=parsed.get("text_hash"), detail=parsed.get("detail"), manual=manual,
        kind=cfg.get("kind", "national"), issuer=cfg.get("issuer"))


def _failed(cfg: dict, prev: dict | None, error: str) -> AnchorReading:
    """Keep the last known value and its date, marked failed, as the spec requires."""
    log.warning("%s failed: %s", cfg["id"], error)
    if prev and prev.get("raw") is not None:
        kept = AnchorReading.model_validate(prev)
        return kept.model_copy(update={"status": "failed", "error": error})
    return AnchorReading(id=cfg["id"], country=cfg["country"], name=cfg["name"], url=cfg["url"],
                         scale=cfg["scale"], raw=None, level=None, normalized=None, as_of=None,
                         status="failed", error=error, kind=cfg.get("kind", "national"),
                         issuer=cfg.get("issuer"))


def _read_one(cfg: dict, now: datetime, manual_levels: dict) -> AnchorReading:
    parser = cfg["parser"]
    if parser == "manual":
        entry = manual_levels.get(cfg["id"])
        if not entry:
            raise AnchorError("no value in manual_anchors.yaml")
        entered = entry["entered_on"]
        old = (now.date() - entered).days > MANUAL_MAX_AGE_DAYS
        return _reading(cfg, now, {
            "raw": entry["raw"], "since": entry.get("since"),
            # Dated by when it was typed in, never by the run, so the page does not imply a check.
            "as_of": datetime(entered.year, entered.month, entered.day, tzinfo=UTC),
            "stale_reason": f"entered by hand on {entered}; please check the official page"
            if old else None}, manual=True)
    r = get(cfg.get("api", cfg["url"]))
    if parser == "fcdo":
        return _reading(cfg, now, parse_fcdo(r.json()))
    html = r.content.decode("utf-8")  # SIS sends no charset header; all four pages are UTF-8
    if parser == "sis":
        return _reading(cfg, now, parse_sis(html))
    if parser == "ocam":
        return _reading(cfg, now, parse_ocam(html))
    if parser == "nctv":
        return _reading(cfg, now, parse_nctv(html))
    if parser == "mswia":
        return _reading(cfg, now, parse_mswia(html, now.date()))
    raise AnchorError(f"unknown parser {parser!r}")


def anchor_configs() -> list[dict]:
    conf = yaml.safe_load((CONFIG / "anchors.yaml").read_text())
    out = list(conf["anchors"])
    f = conf["fcdo"]
    for cc, slug in f["countries"].items():
        out.append({"id": f"anchor_fcdo_{cc.lower()}", "country": cc, "name": "FCDO travel advice",
                    "parser": "fcdo", "api": f["url"] + slug,
                    "url": f"https://www.gov.uk/foreign-travel-advice/{slug}",
                    "scale": f["scale"], "kind": "travel", "issuer": "GB"})
    return out


def read_all(previous: list[dict], now: datetime | None = None) -> list[AnchorReading]:
    """Read every anchor once. previous is last run's anchors (dicts from latest.json)."""
    now = now or datetime.now(UTC).replace(microsecond=0)
    prev = {a["id"]: a for a in previous}
    manual = yaml.safe_load((CONFIG / "manual_anchors.yaml").read_text()).get("levels") or {}
    out = []
    for cfg in anchor_configs():
        try:
            out.append(_read_one(cfg, now, manual))
        except (AnchorError, FetchError, ValueError, KeyError) as e:
            out.append(_failed(cfg, prev.get(cfg["id"]), f"{type(e).__name__}: {e}"))
    conf = yaml.safe_load((CONFIG / "anchors.yaml").read_text())
    gkg = next(s for s in yaml.safe_load((CONFIG / "sources.yaml").read_text())["sources"]
               if s["adapter"] == "gdelt_gkg")["gkg"]
    for cfg in conf["travel"]:
        out.extend(read_travel(cfg, list(conf["fcdo"]["countries"]), gkg["countries"], prev, now))
    return out
