"""Date parsing for scraped pages, including Slovak, Polish and Dutch month names."""

import re
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

MONTHS = {
    # Slovak genitive, as in "23. augusta 2017"
    "januára": 1, "februára": 2, "marca": 3, "apríla": 4, "mája": 5, "júna": 6, "júla": 7,
    "augusta": 8, "septembra": 9, "októbra": 10, "novembra": 11, "decembra": 12,
    # Polish genitive, as in "30 listopada 2026" ("marca" is March in both languages)
    "stycznia": 1, "lutego": 2, "kwietnia": 4, "maja": 5, "czerwca": 6,
    "lipca": 7, "sierpnia": 8, "września": 9, "października": 10, "listopada": 11, "grudnia": 12,
    # Dutch, as in "12 december 2023"
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6, "juli": 7,
    "augustus": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
}
_DMY = re.compile(r"(\d{1,2})\.?\s+([^\W\d_]+)\s+(\d{4})")


def parse_local_date(text: str) -> date:
    """'23. augusta 2017', '30 listopada 2026', '12 december 2023' -> date. Raises ValueError."""
    m = _DMY.search(text)
    if not m:
        raise ValueError(f"no date in {text!r}")
    month = MONTHS.get(m.group(2).lower())
    if month is None:
        raise ValueError(f"unknown month {m.group(2)!r}")
    return date(int(m.group(3)), month, int(m.group(1)))


def parse_listed(text: str, fmt: str, tz: str = "UTC") -> tuple[datetime, bool]:
    """A date from a news list. fmt is a strptime format or 'iso'. Returns (UTC datetime,
    date_only); date_only is True when the format carries no time of day."""
    text = text.strip()
    if fmt == "iso":
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(tz))
        return dt.astimezone(UTC), False
    dt = datetime.strptime(text, fmt)
    date_only = not any(c in fmt for c in ("%H", "%I", "%M"))
    return dt.replace(tzinfo=ZoneInfo(tz)).astimezone(UTC), date_only
