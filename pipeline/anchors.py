"""Official threat levels (anchors) read from government pages, and UK FCDO wording.

Each parser returns the raw value exactly as the page shows it; a value outside the
configured scale, zero matches or several matches raise, so a layout change fails loudly
instead of reporting a wrong level. A failed read keeps the last known value with its date.
"""

import hashlib
import logging
import re
from datetime import UTC, date, datetime
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

from .adapters.base import FetchError, get
from .adapters.dates import parse_local_date
from .models import AnchorReading

CONFIG = Path(__file__).parent / "config"
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
    return {"raw": raw, "detail": " | ".join(others) or None,
            "expired": expiry is not None and expiry < today}


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


def _reading(cfg: dict, now: datetime, parsed: dict, manual: bool = False) -> AnchorReading:
    raw = parsed["raw"]
    if raw not in cfg["scale"]:
        raise AnchorError(f"value {raw!r} is not on the scale {cfg['scale']}")
    level = cfg["scale"].index(raw) + 1
    return AnchorReading(
        id=cfg["id"], country=cfg["country"], name=cfg["name"], url=cfg["url"],
        scale=cfg["scale"], raw=raw, level=level,
        normalized=round((level - 1) / (len(cfg["scale"]) - 1), 3), since=parsed.get("since"),
        as_of=now, status="stale" if parsed.get("expired") else "ok",
        error="the order behind this level has expired" if parsed.get("expired") else None,
        text_hash=parsed.get("text_hash"), detail=parsed.get("detail"), manual=manual)


def _failed(cfg: dict, prev: dict | None, error: str) -> AnchorReading:
    """Keep the last known value and its date, marked failed, as the spec requires."""
    log.warning("%s failed: %s", cfg["id"], error)
    if prev and prev.get("raw") is not None:
        kept = AnchorReading.model_validate(prev)
        return kept.model_copy(update={"status": "failed", "error": error})
    return AnchorReading(id=cfg["id"], country=cfg["country"], name=cfg["name"], url=cfg["url"],
                         scale=cfg["scale"], raw=None, level=None, normalized=None, as_of=None,
                         status="failed", error=error)


def _read_one(cfg: dict, now: datetime, manual_levels: dict) -> AnchorReading:
    parser = cfg["parser"]
    if parser == "manual":
        entry = manual_levels.get(cfg["id"])
        if not entry:
            raise AnchorError("no value in manual_anchors.yaml")
        return _reading(cfg, now, {"raw": entry["raw"], "since": entry.get("since")}, manual=True)
    r = get(cfg["url"])
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
                    "parser": "fcdo", "url": f["url"] + slug, "scale": f["scale"]})
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
    return out
