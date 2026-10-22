"""Export the JSON Schema of the run file: python -m pipeline.tools.export_schema OUT.json

The frontend generates its TypeScript types from this file (npm run gen:types).
"""

import json
import sys
from pathlib import Path

from ..models import Run


def main() -> None:
    out = Path(sys.argv[1])
    out.write_text(json.dumps(Run.model_json_schema(mode="serialization"), indent=2) + "\n")


if __name__ == "__main__":
    main()
