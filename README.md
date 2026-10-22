# Threat dashboard

A free, static dashboard for Slovakia and the EU, refreshed twice a day (04:05 and 13:05 UTC)
from open sources. Its levels are a **dashboard indicator**, not an official threat assessment;
the official Slovak level is published by the SIS.

- `pipeline/`: Python 3.12 data pipeline, run by `.github/workflows/pipeline.yml`.
  It writes JSON to the `data` branch, which the site reads directly.
- `web/`: Vite + React + TypeScript site, deployed by Netlify from `main` only.

## Run locally

```bash
uv sync
uv run pytest
uv run python -m pipeline.main --fixtures --state-dir /tmp/td-state
cd web && npm install && npm run dev
```

The pipeline's pydantic models (`pipeline/models.py`) define the data format. After changing
them, regenerate the schema and the frontend types:

```bash
uv run python -m pipeline.tools.export_schema web/src/types/run.schema.json
cd web && npm run gen:types
```
