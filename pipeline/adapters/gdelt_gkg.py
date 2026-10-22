"""GDELT 2.0 GKG 15-minute files: daily article counts per theme and country.

These counts are the media baselines (component M and theatre activity). Each run reads only
the files it has not processed yet, so the twice-daily runs neither miss nor double-count a
slice. A file is about 4 MB zipped. GDELT's CDN caches a 404 for an hour, and other users
request new files before they exist, so a fresh file often answers 404 for its first hour (seen
on 2026-10-22). Only files at least 90 minutes older than the newest listed one are read; newer
ones wait for the next run, which picks up everything not yet processed.

GKG 2.1 columns (tab-separated, 0-based): 1 DATE, 8 V2Themes ("THEME,offset;..."),
10 V2Locations ("type#name#FIPS#adm1#adm2#lat#lon#featureid#offset;..."), 15 V2Tone
("tone,positive,negative,..."; the first value is the article's average tone, -100 to 100).
"""

import io
import re
import zipfile
from datetime import UTC, datetime, timedelta

from .base import FetchError, get

BASE = "https://data.gdeltproject.org/gdeltv2/"
STEP = timedelta(minutes=15)
SETTLE = timedelta(minutes=90)
_TS = re.compile(r"/(\d{14})\.gkg\.csv\.zip")


def latest_listed() -> datetime:
    r = get(BASE + "lastupdate.txt")
    m = _TS.search(r.text)
    if not m:
        raise FetchError("no gkg file in lastupdate.txt")
    return datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=UTC)


def pending_files(newest: datetime, done: set[str], max_back: timedelta) -> list[str]:
    """Timestamps (YYYYMMDDHHMMSS) from newest back to max_back that are not in done,
    stopping at the first one already processed."""
    out, ts = [], newest
    while ts > newest - max_back:
        key = ts.strftime("%Y%m%d%H%M%S")
        if key in done:
            break
        out.append(key)
        ts -= STEP
    return out[::-1]


Nested = dict[str, dict[str, dict[str, float]]]  # day -> theme -> country -> value


def count_file(raw: bytes, themes: set[str], fips: dict[str, str], eu: set[str],
               ) -> tuple[Nested, Nested]:
    """({day: {theme: {country: articles}}}, the same with summed tone). Each article counts
    once per theme and country; 'EU' counts it once if it mentions any EU member state; 'ALL'
    counts every article."""
    counts: Nested = {}
    tones: Nested = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        name = z.namelist()[0]
        with z.open(name) as f:
            for line in io.TextIOWrapper(f, encoding="utf-8", errors="replace"):
                cols = line.split("\t")
                if len(cols) < 11:
                    continue
                found = {t.split(",", 1)[0] for t in cols[8].split(";") if t} & themes
                if not found:
                    continue
                places = set()
                for loc in cols[10].split(";"):
                    parts = loc.split("#")
                    if len(parts) > 2 and parts[2] in fips:
                        places.add(fips[parts[2]])
                keys = places | {"ALL"} | ({"EU"} if places & eu else set())
                day = f"{cols[1][:4]}-{cols[1][4:6]}-{cols[1][6:8]}"
                try:
                    tone = float(cols[15].split(",", 1)[0]) if len(cols) > 15 else None
                except ValueError:
                    tone = None
                by_theme = counts.setdefault(day, {})
                tone_theme = tones.setdefault(day, {})
                for theme in found:
                    by_country = by_theme.setdefault(theme, {})
                    tone_country = tone_theme.setdefault(theme, {})
                    for k in keys:
                        by_country[k] = by_country.get(k, 0) + 1
                        if tone is not None:
                            tone_country[k] = round(tone_country.get(k, 0.0) + tone, 3)
    return counts, tones


def fetch(source: dict, done: set[str]) -> tuple[list[dict], list[str], str | None]:
    """Process pending files. Returns (records, missing, error); each record is
    {"file": timestamp, "counts": {...}}."""
    cfg = source["gkg"]
    themes, fips = set(cfg["themes"]), cfg["countries"]
    eu = set(cfg["eu"])
    newest = latest_listed() - SETTLE
    records, missing = [], []
    for ts in pending_files(newest, done, timedelta(hours=cfg["max_hours"])):
        try:
            r = get(f"{BASE}{ts}.gkg.csv.zip", retries=1, backoff_s=5)
        except FetchError as e:
            missing.append(f"{ts} ({e})")
            continue
        try:
            counts, tones = count_file(r.content, themes, fips, eu)
            records.append({"file": ts, "counts": counts, "tone": tones})
        except zipfile.BadZipFile:
            missing.append(f"{ts} (bad zip)")
    error = f"{len(missing)} files missing, first: {missing[0]}" if missing else None
    return records, missing, error
