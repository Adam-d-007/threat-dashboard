# Threat dashboard

A static dashboard for Slovakia and the EU, refreshed every hour from open sources; the threat
level and the brief are recomputed twice a day. Its levels are a **dashboard indicator**, not an
official threat assessment; the official Slovak level is published by the SIS.

- `monitor/`: the pipeline (Python 3.12), run every hour by `.github/workflows/collect.yml`.
  It labels articles, matches them to incidents, scores and writes the brief with Claude
  (Gemini and Groq as backup), and writes JSON under `v2/` on the `data` branch, which the site
  reads directly. Design: `docs/plans/2026-11-12-rebuild-design.md`.
- `pipeline/`: the first pipeline's code. It no longer runs; `monitor/` still uses its fetching
  adapters, official-level readers and scoring formulas.
- `web/`: Vite + React + TypeScript site, deployed by Netlify from `main` only.

## Run locally

```bash
uv sync
uv run pytest
uv run python -m monitor --state-dir <a checkout of the data branch> --no-ai --no-fetch
cd web && npm install && npm run dev
```

The pydantic models (`monitor/models.py`, and `pipeline/models.py` for the shapes they reuse)
define the data format. After changing them, regenerate the schemas and the frontend types:

```bash
uv run python -m pipeline.tools.export_schema web/src/types/run.schema.json
uv run python -m monitor.tools.export_schema web/src/types/v2.schema.json
cd web && npm run gen:types
```
