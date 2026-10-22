# Build status against the spec

Audited 2026-10-22 against the build spec (Oct 22, 2026). Legend: **done**, **partial**,
**not started**, **waiting on Adam**, **blocked** (outside our control).

## Summary

| Area | State |
|---|---|
| Phase 1, heartbeat | Done, except: no scheduled run has fired yet (all runs so far were started by hand) |
| Phase 2, sources | Mostly done: 28 of 41 sources live; ACLED and ReliefWeb wait on access; GDELT GKG not built |
| Phase 3, processing (LLM classification, geocoding, clustering) | **Not started.** Needs Gemini and Groq keys |
| Phase 4, scoring and calibration | **Not started.** The level and index do not exist yet |
| Geopolitics computation (theatres, activity, brief) | **Not started** |
| Phase 5, frontend | Mostly done on sample data; a few panels missing |
| Phase 6, hardening (alerts, squash, runbook, 14 days) | **Not started** |

Without phases 3 and 4 the site can show official levels, TE-SAT figures and the latest
reports, but no dashboard indicator. That is the core of the product.

## Hard rules

| # | Rule | State |
|---|---|---|
| 1 | Zero recurring cost | Done. Note: Netlify's 300 credits are shared with the other MCS sites |
| 2 | Indicator labelled, next to the SIS level | Done in the frontend |
| 3 | Every score traceable | Frontend ready; no scores exist yet |
| 4 | Media against a rolling baseline | Not started (needs GDELT baselines) |
| 5 | A failing source never breaks a run | Done and tested |
| 6 | No secrets in repo or frontend | Done (gitleaks in CI) |
| 7 | LLM output schema-validated, rules fallback | Not started |
| 8 | Events and organisations, not private individuals | Applies once classification exists |

## Phase 1, heartbeat

- [x] Pipeline, data branch, frontend shell, CI with tests and gitleaks
- [x] Data age shown; red after 14 h (tested)
- [x] Netlify deploy count unchanged by data commits (checked 2026-10-22)
- [ ] **Two scheduled runs in a row.** Workflows are active and the cron is valid, but GitHub
      had not fired a single scheduled run by 10:58 UTC (collector due hourly from 08:35).
      Check again after the 13:05 pipeline slot.

## Phase 2, sources

- [x] 41 registry entries, every one either verified or disabled with a written reason
- [x] RSS, HTML-scrape and JSON adapters; robots.txt respected; health records; sources page
- [x] Official levels: SIS (level 2 since 23 Aug 2017), Belgium, Netherlands, Poland,
      UK FCDO for the EU-27; France entered by hand (its sites block automated reading)
- [x] Hourly RSS collector with a 48-hour buffer
- [x] TE-SAT 2026 figures entered and shown
- [ ] **ACLED**: adapter written from the docs and switched off; waiting for credentials and
      the tier check (`pipeline/tools/acled_check.py`)
- [ ] **ReliefWeb**: adapter not written; waiting for the approved appname
- [ ] **GDELT GKG / Events files** (theme and location counts for baselines): not built
- [ ] **GDELT DOC TimelineVolRaw** calls for baselines: not built
- [ ] **GDELT DOC queries**: only 1 of the planned set (SK sources, terrorism theme)
- [ ] **SIS annual report** in manual_anchors.yaml: empty
- [ ] **GTD aggregates** (`static/gtd_aggregates.json`): needs Adam's GTD download from START
- Blocked and left out: MZV, GLOBSEC, ISW, EUvsDisinfo, Euractiv (bot walls; GDELT does not
  index them), DW and PAP (explicit opt-outs). Telex, EEAS and ECFR are unreachable from
  GitHub's servers and replaced (Index.hu, Council feed, ECFR through GDELT).
- Known weakness: GDELT answers GitHub's shared addresses with HTTP 429 in roughly every
  second run.
- Bug found and fixed on dev: canonical URLs broke minv.sk article links.

## Phase 3, processing (not started)

- [ ] `keywords.yaml` prefilter terms in EN, SK, CS, DE, HU, PL, FR, UK (Adam to review SK/CS)
- [ ] GDELT theme allowlist checked against the GKG theme list
- [ ] Prefilter stage (cap at 600 items, by tier then recency)
- [ ] Near-duplicate dedupe (rapidfuzz, 48 h, same language) and `also_reported_by`
- [ ] LLM client: Gemini with Groq fallback, 10 requests/min limit, model check each run
- [ ] Classification prompts (items wrapped as data), pydantic validation, one retry,
      rules fallback, `unclassified`; budget 30 calls
- [ ] Language detection where a feed does not declare one
- [ ] Geocoding with the local GeoNames cities15000 file (cached in Actions)
- [ ] Event clustering (event_key; same type and country, 50 km, 1 day) merged with
      `events.json`; corroboration (2 domains or 1 Tier A)
- [ ] Acceptance: SK/CS/EN fixture event becomes one cluster with 3 domains; `--no-llm` run;
      prompt-injection fixture; LLM calls logged and kept at 45 or fewer

## Phase 4, scoring and calibration (not started)

- [ ] `scoring.yaml` with every weight, floor, threshold and gate
- [ ] Components E, M, A, L with the shared f(r) curve
- [ ] Gates (floor 2, SK caps at 2 and 3, EU cap at 3), smoothing (EMA 0.5), hysteresis
- [ ] LLM assessment per region and the disagreement rule
- [ ] `timeseries.json`, `baselines.json`, `events.json` on the data branch
- [ ] 180-day backfill for baselines (see the open question about measuring E consistently)
- [ ] Replays: Bratislava 2022, Vienna 2020, Solingen 2024, Villach 2025; quiet-window check
- [ ] `docs/SCORING.md`

## Geopolitics (not started)

- [ ] `theatres.yaml` (six theatres) and `watchlist.yaml`
- [ ] Activity against the 90-day median, ACLED weekly comparison, tone
- [ ] Top developments and the Slovak angle (LLM)
- [ ] Daily brief (one LLM call per run), dates extracted from news marked unverified

## Phase 5, frontend

- [x] Terrorism tab (SK/EU), geopolitics, sources and method pages; EN/SK; dark/light; phone
- [x] Level strip beside the official level, banners, index history, component breakdown,
      assessment, changes, incident map, table, ideology mix, TE-SAT base rates
- [x] Sample data on the dev deploy only, labelled on every page; production shows real data
- [ ] Run picker (last 14 days from `runs/`)
- [ ] Gate markers on the index history
- [ ] Ideology mix side by side with the TE-SAT distribution
- [ ] Geopolitics map (needs items tagged by theatre, phase 3)
- [ ] Method page rendering `docs/SCORING.md` (static text for now)
- [ ] ACLED attribution on pages that show ACLED data (required by ACLED's terms)
- [ ] GTD history in base rates
- [ ] Acceptance: every panel with the five fixture cases; load under 3 s on throttled 4G

## Phase 6, hardening (not started)

- [ ] `pipeline-failure` GitHub issue on failure or two partial runs; comment when fixed
- [ ] Issue when the SIS level paragraph changes (the change is detected already)
- [ ] `squash-data.yml` monthly rewrite of the data branch (must pause both workflows)
- [ ] `docs/RUNBOOK.md`, including the 60-day inactivity rule for scheduled workflows
- [ ] Source "stale" after 6 runs with zero items where items are normal
- [ ] Final run-status rule (GDELT DOC, LLM and 10 Tier B sources must succeed)
- [ ] 14 days (28 runs) without manual fixes

## Waiting on Adam

- [ ] Gemini API key as Actions secret `GEMINI_API_KEY`, plus its daily limit from AI Studio
- [ ] Groq API key as Actions secret `GROQ_API_KEY`
- [ ] ACLED: secrets `ACLED_EMAIL` and `ACLED_PASSWORD`, then the access check
- [ ] ReliefWeb: approved appname (requested 2026-10-22)
- [ ] GTD download from START (registration form)
- [ ] Review of the Slovak and Czech prefilter terms once written
