"""Yearly GTD counts for Slovakia and the EU-27, from START's Global Terrorism Database file.

python -m pipeline.tools.gtd_aggregates FILE   writes static/gtd_aggregates.json

FILE is the GTD download (.csv, or .xlsx with `uv run --with openpyxl`). Its licence forbids
publishing the raw data, so the file stays outside the repository and only yearly counts are
written: incidents (GTD counts failed attacks too) and deaths, per year. The EU is today's 27
member states for every year, so the series measures the same territory throughout. Run it on
Adam's Mac, never in Actions.

GTD names countries as they were at the time. Former states that map to one present member
(West and East Germany) are merged into it. Czechoslovakia counts for the EU but not for
Slovakia, because GTD does not say which part an incident was in. Yugoslavia and the Soviet
Union are left out (most of their territory is outside the EU). Any other European country
name the mapping does not know stops the tool, so nothing is dropped silently.
"""

import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

OUT = Path(__file__).parents[2] / "static" / "gtd_aggregates.json"
SOURCE = "https://www.start.umd.edu/data-tools/GTD"

# GTD country_txt -> ISO code; "EU" for a former state wholly inside today's EU.
EU_NAMES = {
    "Austria": "AT", "Belgium": "BE", "Bulgaria": "BG", "Croatia": "HR", "Cyprus": "CY",
    "Czech Republic": "CZ", "Czechia": "CZ", "Denmark": "DK", "Estonia": "EE", "Finland": "FI",
    "France": "FR", "Germany": "DE", "West Germany (FRG)": "DE", "East Germany (GDR)": "DE",
    "Greece": "GR", "Hungary": "HU", "Ireland": "IE", "Italy": "IT", "Latvia": "LV",
    "Lithuania": "LT", "Luxembourg": "LU", "Malta": "MT", "Netherlands": "NL", "Poland": "PL",
    "Portugal": "PT", "Romania": "RO", "Slovak Republic": "SK", "Slovakia": "SK",
    "Slovenia": "SI", "Spain": "ES", "Sweden": "SE", "Czechoslovakia": "EU",
}
# European countries outside today's EU, and former states left out (see the docstring).
OUTSIDE = {
    "Albania", "Andorra", "Belarus", "Bosnia-Herzegovina", "Gibraltar", "Iceland", "Kosovo",
    "Liechtenstein", "Macedonia", "North Macedonia", "Moldova", "Montenegro", "Norway",
    "Russia", "Serbia", "Serbia-Montenegro", "Switzerland", "Ukraine", "United Kingdom",
    "Vatican City", "Yugoslavia", "Soviet Union", "Monaco", "San Marino", "Armenia",
    "Azerbaijan", "Georgia", "Turkey", "Northern Ireland",
}
EUROPE = {"Western Europe", "Eastern Europe"}


def rows(path: Path):
    if path.suffix.lower() == ".xlsx":
        try:
            import openpyxl
        except ImportError:
            sys.exit("Reading .xlsx needs openpyxl: uv run --with openpyxl python -m "
                     "pipeline.tools.gtd_aggregates FILE")
        sheet = openpyxl.load_workbook(path, read_only=True).active
        it = sheet.iter_rows(values_only=True)
        header = [str(h) for h in next(it)]
        for r in it:
            yield dict(zip(header, r, strict=False))
    else:
        with path.open(encoding="latin-1", newline="") as f:
            yield from csv.DictReader(f)


def aggregate(records) -> dict:
    years: dict[str, dict[int, dict[str, int]]] = {"SK": {}, "EU": {}}
    unknown = set()
    for r in records:
        name = str(r["country_txt"]).strip()
        code = EU_NAMES.get(name)
        if code is None:
            if str(r.get("region_txt", "")).strip() in EUROPE and name not in OUTSIDE:
                unknown.add(name)
            continue
        year = int(r["iyear"])
        killed = r.get("nkill")
        deaths = int(float(killed)) if killed not in (None, "") else 0
        for region in ("EU", "SK") if code == "SK" else ("EU",):
            y = years[region].setdefault(year, {"incidents": 0, "deaths": 0})
            y["incidents"] += 1
            y["deaths"] += deaths
    if unknown:
        raise SystemExit(f"Unmapped European country names, add them to EU_NAMES or OUTSIDE: "
                         f"{sorted(unknown)}")
    if not years["EU"]:
        raise SystemExit("No EU incidents found: is this the GTD file?")
    first, last = min(years["EU"]), max(years["EU"])
    series = {region: [{"year": y, **years[region].get(y, {"incidents": 0, "deaths": 0})}
                       for y in range(first, last + 1)] for region in years}
    return {"source": SOURCE, "data_ends": last, "generated": datetime.now(UTC).date().isoformat(),
            "SK": series["SK"], "EU": series["EU"]}


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    data = aggregate(rows(Path(sys.argv[1])))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1) + "\n")
    eu = sum(y["incidents"] for y in data["EU"])
    sk = sum(y["incidents"] for y in data["SK"])
    print(f"wrote {OUT}: {data['EU'][0]['year']}-{data['data_ends']}, EU {eu} incidents, "
          f"Slovakia {sk}")


if __name__ == "__main__":
    main()
