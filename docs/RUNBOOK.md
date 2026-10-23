# Runbook: what to do when something breaks

The pipeline is built to keep running when parts fail: a failing source never stops a run, a
failed language model falls back to rules, and a broken run never replaces the last good data.
Most problems therefore show up as a banner on the site or a GitHub issue, not as a dead site.

Where to look:

- **Actions:** https://github.com/Adam-d-007/threat-dashboard/actions (every run and its log)
- **Issues:** https://github.com/Adam-d-007/threat-dashboard/issues (alerts, emailed to Adam)
- **Sources page** on the site: every source with its status, last success and error text
- **Data branch:** https://github.com/Adam-d-007/threat-dashboard/tree/data (the raw JSON)

## The site is red: "data is more than 14 hours old"

A scheduled run was missed. Check, in order:

1. **Actions → pipeline.** Is the latest run failed, or is there no run since the last slot?
2. **Scheduled runs dropped.** GitHub can delay or drop scheduled runs under load (the 04:05
   slot once started at 09:16). Each run has two backup slots, and every collector run starts
   the pipeline when its slot is more than 20 minutes overdue (the "Start the pipeline if its
   slot is overdue" step in a collect run's log says what it did). If neither ran, start a run
   by hand: Actions → pipeline → Run workflow → branch `main` → Run workflow. The outside timer
   in SETUP.md step 8 keeps the collector, and so the watchdog, running every hour.
3. **Workflows disabled after 60 days.** In a public repository, GitHub disables scheduled
   workflows when there has been no repository activity for 60 days. GitHub's documentation
   does not define "activity", and it is not confirmed whether the pipeline's own commits (made
   by github-actions[bot] on the `data` branch, not the default branch) count. A commit pushed
   to `main` by a person does count. If Actions shows "This scheduled workflow is disabled",
   open each of **pipeline**, **collect** and **squash-data** in Actions and click
   **Enable workflow**. To avoid it, push any small change to `main` at least every 50 days.

## A `pipeline-failure` issue opened

It opens when a run fails, or when two runs in a row are partial. The issue lists the sources
that were not ok. It closes itself when a run is fully ok.

- **A run failed:** open the run in Actions and read the red step's log. If the pipeline step
  crashed, the previous `latest.json` stays live; the site shows the age banner after 14 hours.
- **Partial runs:** a run is partial when any source failed, the language model fell back to
  rules, fewer than 10 press sources succeeded, or a GDELT DOC query has not succeeded in 24
  hours. GDELT DOC is queried by the hourly **collect** workflow, and the pipeline itself retries
  any query without a success in 6 hours, because GDELT answers GitHub's servers with HTTP 429
  (too many requests) about every second call. Each query asks for everything since its own last
  success, up to a day back, so nothing is lost until a query has failed for a whole day. If GDELT DOC stays failed for
  a day, open the latest collect run and read the `gdelt_doc` lines in its log.

## A source shows failed or stale

- **failed:** an error in this run; its last good items are kept. One failed run needs no action.
- **stale:** no success for 48 hours, or six runs in a row without items.
- Check the error text on the sources page. Common causes:
  - **HTTP 403 or a bot wall:** the site started blocking automated requests. Check in a
    browser; if the site now forbids it, disable the source with a note in `sources.yaml`.
  - **"no items match":** the page layout changed; the selectors in `sources.yaml` need updating.
  - **certificate errors:** the site changed its certificate chain; see `pipeline/certs/`.
- Never re-enable a source that blocks or forbids automated access.

## The language model fell back to rules

The run marks `llm: fallback` and the assessment panel says so. Common causes:

- **Gemini overloaded (HTTP 503):** the client tries Gemini's next model, then Groq. Nothing to do.
- **A key stopped working (HTTP 401 or 403):** create a new key and replace the secret
  (`GEMINI_API_KEY` or `GROQ_API_KEY`) under Settings → Secrets and variables → Actions.
- **A model was retired:** the client picks the newest available model on its own and logs a
  warning; update `prefer` in `pipeline/config/scoring.yaml` when convenient.
- **Free-tier quota used up:** the run continues on Groq or rules; it resets the next day.

## An `sis-change` issue opened

The SIS NBAC page changed: either the official level or only the wording of the paragraph that
states it. Open https://www.sis.gov.sk/o-nas/nbac-sto.html. If the level changed, the site
already shows it. If only the wording changed, check that `parse_sis` in `pipeline/anchors.py`
still reads the right sentence (run `uv run pytest` after any change).

## Yearly figures entered by hand

Two sources publish once a year as PDFs and are typed into
`pipeline/config/manual_anchors.yaml`:

- **Europol TE-SAT** (usually June): update `tesat`, moving the old figures to
  `previous_year`. The page numbers are noted beside each figure.
- **SIS annual report** (`sis_annual`, usually mid-year, at
  https://www.sis.gov.sk/pre-vas/sprava-o-cinnosti.html): rewrite the four points in your own
  words from the terrorism and extremism sections. Never name individuals.

Or ask Claude to do it from the new PDF. The site shows whatever year is entered, with its link.

## France changed its Vigipirate posture

SGDSN's site blocks automated reading, so France is entered by hand. Edit
`pipeline/config/manual_anchors.yaml` (`raw`, `since`, `entered_on`), or tell Claude the new
posture. The site marks the value stale 180 days after `entered_on`.

## Switching on ReliefWeb

- **ReliefWeb:** when the appname is approved, add it as the Actions *variable*
  `RELIEFWEB_APPNAME` (Settings → Secrets and variables → Actions → Variables) and set
  `enabled: true` for `reliefweb`.

## Monthly squash

On the 1st of each month `squash-data` rewrites the `data` branch to one commit with exactly the
same files. To check it by hand: Actions → squash-data → Run workflow (dry run is ticked by
default). If a real run fails with "stale info", the collector pushed at the same moment; run it
again.

## Deploying the site

Netlify builds production from `main` only, and each production deploy costs 15 of the team's
300 monthly credits, shared with the other MCS sites. Work on `dev` (its deploys are free) and
merge to `main` in batches, at most 12 times a month. Pushes that do not touch `web/` skip the
build entirely.

## Secrets

Secrets live only in GitHub (Settings → Secrets and variables → Actions). They are not visible
in the repository or the logs, and nobody can read them back, only replace them. Never paste a
key into a file, an issue or a chat.
