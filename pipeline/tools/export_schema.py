"""Export JSON Schema: python -m pipeline.tools.export_schema OUT.json

Covers latest.json (Run) and timeseries.json (Timeseries). The frontend generates its
TypeScript types from this file (npm run gen:types).
"""

import json
import sys
from pathlib import Path

from pydantic.json_schema import models_json_schema

from ..models import Run, Timeseries


def main() -> None:
    out = Path(sys.argv[1])
    _, schema = models_json_schema([(Run, "serialization"), (Timeseries, "serialization")],
                                   title="Threat dashboard data")
    out.write_text(json.dumps(schema, indent=2) + "\n")


if __name__ == "__main__":
    main()
