"""Build pipeline/data/gazetteer.tsv.gz from GeoNames cities15000.txt and countryInfo.txt.

python -m pipeline.tools.build_gazetteer DIR   (DIR holds the two files, downloaded by hand)

GeoNames data, CC BY 4.0, https://www.geonames.org. download.geonames.org disallows automated
clients in robots.txt, so the pipeline never downloads it; this compact copy is committed
instead and rebuilt by hand when needed. Alternate names are kept only in Latin, Cyrillic and
Greek script, which covers every language the pipeline reads.
"""

import gzip
import re
import sys
from pathlib import Path

OUT = Path(__file__).parents[1] / "data" / "gazetteer.tsv.gz"
_SCRIPT_OK = re.compile(r"^[\u0000-ɏͰ-ϿЀ-ӿḀ-ỿ' .,-]+$")


def main() -> None:
    src = Path(sys.argv[1])
    rows = []
    for line in (src / "cities15000.txt").read_text(encoding="utf-8").splitlines():
        c = line.split("\t")
        alts = sorted({a for a in c[3].split(",") if a and _SCRIPT_OK.match(a)} - {c[1], c[2]})
        rows.append("\t".join(["P", c[8], c[1], c[2], ",".join(alts), c[4], c[5], c[14]]))
    for line in (src / "countryInfo.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        c = line.split("\t")
        rows.append("\t".join(["C", c[0], c[4], c[5]]))  # country code, name, capital
    header = ("# GeoNames (https://www.geonames.org), CC BY 4.0. "
              "P: kind cc name asciiname alternates lat lon population; C: kind cc name capital\n")
    OUT.write_bytes(gzip.compress((header + "\n".join(rows) + "\n").encode(), mtime=0))
    print(f"{len(rows)} rows, {OUT.stat().st_size // 1024} KB -> {OUT}")


if __name__ == "__main__":
    main()
