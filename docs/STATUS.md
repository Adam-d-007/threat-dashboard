# Build status against the spec

Audited 2026-10-22 against the build spec (Oct 22, 2026). Legend: **done**, **partial**,
**waiting on Adam**, **waiting on others** (outside our control), **waiting on time**.

## Summary

| Area | State |
|---|---|
| Phase 1, heartbeat | Done; scheduled runs not yet seen firing from `main` (see below) |
| Phase 2, sources | Done for everything open to us: 29 of 41 live. ACLED and ReliefWeb wait on their access; 7 need the publishers' permission; 3 are unreachable from GitHub and replaced |
| Phase 3, processing | Done |
| Phase 4, scoring and calibration | Done; weights are reviewed after four weeks of live data |
| Geopolitics | Done; ACLED comparison switches on with ACLED access |
| Phase 5, frontend | Done; the GTD history appears once Adam's GTD download is aggregated |
| Phase 6, hardening | Done, except the 14 unattended days, which can only start after the merge to `main` |

## Hard rules

| # | Rule | State |
|---|---|---|
| 1 | Zero recurring cost | Done. Netlify's 300 credits are shared with the other MCS sites; production deploys are capped at 12 a month |
| 2 | Indicator labelled, next to the SIS level | Done |
| 3 | Every score traceable | Done: components, inputs, gates and events behind each number |
| 4 | Media against a rolling baseline | Done: GDELT GKG counts against their 90-day median |
| 5 | A failing source never breaks a run | Done and tested |
| 6 | No secrets in repo or frontend | Done (gitleaks in CI; keys only as Actions secrets) |
| 7 | LLM output schema-validated, rules fallback | Done and tested |
| 8 | Events and organisations, not private individuals | Dropped by Adam on 2026-10-22, accepting the GDPR risk: the LLM may name people its sources name. The SIS summary names nobody |

## Phase 1, heartbeat

- [x] Pipeline, data branch, frontend shell, CI with tests and gitleaks
- [x] Data age shown; red after 14 h (tested)
- [x] Netlify deploy count unchanged by data commits (checked 2026-10-22)
- [ ] **Two scheduled runs in a row.** Merged to `main` on 2026-10-22 at 17:00 UTC; the first
      scheduled pipeline slots are 04:05 and 13:05 UTC on 2026-10-23. Check them then.

## Phase 2, sources

- [x] 41 registry entries, every one either verified or disabled with a written reason
- [x] RSS, HTML-scrape and JSON adapters; robots.txt respected; health records; sources page
- [x] Official levels: SIS (level 2 since 23 Aug 2017), Belgium, Netherlands, Poland,
      UK FCDO for the EU-27; France entered by hand (its sites block automated reading)
- [x] Hourly collector with a 48-hour buffer: RSS and the GDELT DOC queries
- [x] GDELT DOC: four queries (Slovak sources, the neighbours' media, mentions of Slovakia,
      hybrid incidents over Europe), run hourly over 3-hour windows
- [x] GDELT GKG files: daily counts and tone per theme and country in `baselines.json`
- [x] TE-SAT 2026 figures entered and shown
- [x] SIS annual report (2023, the latest published) summarised and shown on the Slovak page
- [ ] **ACLED** (waiting on others): adapter written and switched off. Sign-in works, but the
      read endpoint answers 403: the account has no API access yet (Adam emailed ACLED)
- [ ] **ReliefWeb** (waiting on others): adapter written and tested; waiting for the approved
      appname (requested 2026-10-22)
- [ ] **GTD aggregates** (waiting on Adam, optional): `pipeline.tools.gtd_aggregates` and the
      chart are built and tested; they need the GTD download from START
- Blocked and left out: MZV, GLOBSEC, ISW, EUvsDisinfo, Euractiv (bot walls; GDELT does not
  index them), DW and PAP (explicit opt-outs). Telex, EEAS and ECFR are unreachable from
  GitHub's servers and replaced (Index.hu, Council feed, ECFR through GDELT). Request texts
  are in [SETUP.md](SETUP.md).
- Media baselines use GKG theme counts instead of GDELT DOC TimelineVolRaw: see
  [SCORING.md](SCORING.md), "Where the build differs from the spec".

## Phase 3, processing

- [x] Prefilter terms in EN, SK, CS, DE, HU, PL, FR, UK (Slovak and Czech reviewed by Adam)
- [x] GDELT themes checked against the GKG theme list
- [x] Prefilter (official and backbone sources always kept; cap 600, by tier then recency)
- [x] Near-duplicate dedupe (same language, 48 h) and `also_reported_by`
- [x] LLM client: Gemini with Groq fallback, model chosen from the live model list each run,
      retries and a time budget
- [x] Classification in batches, items wrapped as data, pydantic validation, one retry,
      keyword-rules fallback, 7-day cache, call budget
- [x] Language: every source declares one; GDELT reports each article's language
- [x] Geocoding from a committed GeoNames gazetteer (GeoNames' robots.txt forbids automated
      downloads, so the file was built once and committed)
- [x] Event clustering (event_key; same type, country and day within 50 km; similar summaries
      when no place), merged with `events.json`; corroboration (2 domains or 1 Tier A)
- [x] Acceptance: one incident in three languages becomes one event; a `--no-llm` run labels
      every item `rules` or `unclassified`; prompt-injection test; LLM calls logged per run, at
      most 41 (30 classify, 10 assess, 1 brief)

## Phase 4, scoring and calibration

- [x] `scoring.yaml` with every weight, floor, threshold and gate
- [x] Components E, M, A, L with the shared f(r) curve
- [x] Gates (floor 2, SK caps at 2 and 3, EU cap at 3), smoothing (EMA 0.5), hysteresis
- [x] LLM assessment per region and the disagreement rule (a forced disagreement keeps the
      gated rules level, tested)
- [x] `timeseries.json`, `baselines.json`, `events.json` on the data branch
- [x] Provisional until 14 days of event history (instead of a 180-day backfill; see SCORING.md)
- [x] Replays: Bratislava 2022, Vienna 2020, Solingen 2024, Villach 2025, from rebuilt
      incidents and with real media counts from GDELT bulk files; quiet-month check
- [x] `docs/SCORING.md`, rendered on the method page

## Geopolitics

- [x] `theatres.yaml` (six theatres) and `watchlist.yaml`
- [x] Activity against the 90-day median, tone against its 90-day median, 30-day sparkline
- [x] Top developments and the Slovak angle (LLM); daily brief with a source on every line;
      dates from the news marked unverified
- [x] Map of reports with a place, filtered by theatre
- [ ] ACLED weekly comparison: built, shows once ACLED is on

## Phase 5, frontend

- [x] Terrorism tab (SK/EU), geopolitics, sources and method pages; EN/SK; dark/light; phone
- [x] Level strip beside the official level, banners, index history with gate markers,
      component breakdown, assessment, changes, incident map, table
- [x] Ideology mix beside the TE-SAT distribution (attacks and arrests), TE-SAT base rates,
      SIS annual report points
- [x] Run picker (stored runs from `runs/`)
- [x] Method page renders `docs/SCORING.md`
- [x] Attribution: OpenStreetMap, GeoNames, GDELT and TE-SAT in the footer; ACLED wherever
      ACLED figures appear
- [x] Sample data on the dev deploy only, labelled on every page; production shows real data
- [x] Every panel renders with the five fixture cases (tested)
- [x] Load time on Lighthouse's mobile 4G profile (dev deploy, 2026-10-22): first paint
      1.7 s, largest paint 1.7 to 2.6 s, interactive 2.6 to 2.7 s
- [ ] GTD history in base rates: built; shows once `static/gtd_aggregates.json` exists

## Phase 6, hardening

- [x] `pipeline-failure` issue on failure or two partial runs (issue #1 opened on its own)
- [ ] The next fully ok run comments on and closes it: not seen yet. The first run on `main`
      showed the alert step crashing on `runs/index.json` (fixed), and runs stay partial until
      GDELT's rate limit lets the `gdelt_outlets` query through once
- [x] `sis-change` issue when the SIS level paragraph changes
- [x] `squash-data.yml` monthly rewrite of the data branch (dry run by default by hand)
- [x] Squash run once as a dry run and once for real (2026-10-22): 20 commits became 1, the
      file tree identical before and after
- [x] `docs/RUNBOOK.md`, including the 60-day inactivity rule for scheduled workflows
- [x] Source "stale" after 6 empty runs, if it has delivered items before
- [x] Run-status rule (every source, GDELT DOC within 6 h, the LLM, 10 press sources)
- [ ] 14 days (28 runs) without manual fixes (waiting on time; counting from 2026-10-23)

## Waiting on Adam

Step-by-step instructions: [SETUP.md](SETUP.md).

- [ ] GTD download from START (optional, step 5)
- [ ] Permission requests to the blocked sources (optional, step 6)
- [ ] ACLED and ReliefWeb: forward their answers when they arrive
