"""Write the JSON Schema of the published v2 files: python -m monitor.tools.export_schema PATH

The website generates its TypeScript types from this file (npm run gen:types), so the shapes
in monitor/models.py stay the single source of truth. CI fails when either is out of date.
"""

import json
import sys
from pathlib import Path

from pydantic import BaseModel

from ..models import GeopoliticsFile, IncidentsFile, ReportsFile, Status, Summary


class Published(BaseModel):
    """Every file the website reads from v2/ of the data branch."""

    status: Status
    summary: Summary
    incidents: IncidentsFile
    reports: ReportsFile
    geopolitics: GeopoliticsFile


def main() -> None:
    schema = Published.model_json_schema(mode="serialization")
    Path(sys.argv[1]).write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
