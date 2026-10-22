"""Stage 7, geocoding against the committed GeoNames gazetteer (no online geocoder).

A place is matched within its country: exact name (official, ASCII or an alternate such as
"Viedeň" or "Pressburg"), then a close spelling. A country name alone resolves to the capital
with precision "country". The most populous city wins when a name repeats in a country.
"""

import gzip
from functools import lru_cache
from pathlib import Path

from rapidfuzz import fuzz, process

from ..models import Place
from .prefilter import fold

DATA = Path(__file__).parents[1] / "data" / "gazetteer.tsv.gz"
FUZZY_MIN = 92


class Gazetteer:
    def __init__(self, path: Path = DATA):
        self.cities: dict[tuple[str, str], tuple[str, float, float, int]] = {}
        self.by_country: dict[str, list[str]] = {}
        self.countries: dict[str, tuple[str, str]] = {}  # folded name -> (cc, capital)
        self.capital_of: dict[str, str] = {}
        for line in gzip.decompress(path.read_bytes()).decode().splitlines():
            if line.startswith("#"):
                continue
            c = line.split("\t")
            if c[0] == "C":
                self.countries[fold(c[2])] = (c[1], c[3])
                self.capital_of[c[1]] = c[3]
                continue
            cc, name, lat, lon, pop = c[1], c[2], float(c[5]), float(c[6]), int(c[7] or 0)
            for n in {name, c[3], *(c[4].split(",") if c[4] else [])}:
                key = (cc, fold(n))
                if key not in self.cities or self.cities[key][3] < pop:
                    self.cities[key] = (name, lat, lon, pop)
        for cc, n in self.cities:
            self.by_country.setdefault(cc, []).append(n)

    def lookup(self, name: str, country: str) -> Place | None:
        n = fold(name.strip())
        hit = self.cities.get((country, n))
        if hit is None and country in self.by_country:
            best = process.extractOne(n, self.by_country[country], scorer=fuzz.ratio,
                                      score_cutoff=FUZZY_MIN)
            if best:
                hit = self.cities[(country, best[0])]
        if hit:
            return Place(name=hit[0], lat=hit[1], lon=hit[2], precision="city")
        named = self.countries.get(n)
        cc = named[0] if named else (country if n in ("", fold(country)) else None)
        if cc and (cap := self.capital_of.get(cc)) and (c := self.cities.get((cc, fold(cap)))):
            return Place(name=name.strip() or cc, lat=c[1], lon=c[2], precision="country")
        return None


@lru_cache(maxsize=1)
def gazetteer() -> Gazetteer:
    return Gazetteer()


def geocode(refs: list[dict]) -> list[Place]:
    """Place refs from the LLM ({"name", "country"}) to places with coordinates; unknown
    names are dropped."""
    g = gazetteer()
    out = []
    for r in refs:
        place = g.lookup(r["name"], r["country"])
        if place and place not in out:
            out.append(place)
    return out
