# Rebuild design

Date: 2026-11-12. Status: approved by Adam on 2026-11-12; step 0 in progress. Constraints set by Adam: zero budget, make it
work before making it pretty, full rewrite, design before code.

## 1. Goal

A dashboard that updates itself every day without failing, lists each real incident once, and
says honestly what it could not do. Everything runs on free services.

Not in this rebuild: the visual redesign (shelved), any paid API, new indicators.

## 2. What the audit found (2026-10-29 to 2026-11-12)

- 27 of 28 runs ended "partial".
- This morning 33 AI calls gave 11 usable answers: 12 refused, 3 timed out, 7 broken JSON.
- Failed calls count against the 30-call labelling budget; the leftover articles are labelled by
  keyword rules (28% on average, 65% on the worst run), and those labels create incidents.
- The geopolitics brief is about 11,000 tokens; Groq accepts about 8,000 a minute for our models.
  It was written in 3 of 28 runs and carried forward marked "ok".
- Every relevant article becomes an "incident": 56% of the 222 listed have severity 0 ("not an
  incident"). The Kraków attack is one incident with 80 articles plus 10 follow-ups listed
  separately. They weigh 0 in the index, so the score was not inflated; the list was.
- Six different models produced the published numbers, chosen by whichever answered.
- All AI work happens in two bursts a day, which is exactly what free rate limits punish.

## 3. Principles

1. **A queue, not a burst.** AI work is spread over the hourly job: one or two calls an hour
   instead of thirty in ten minutes. Work that fails stays in the queue for the next hour.
2. **No silent substitutes.** If no model labelled an article, it is "waiting", not labelled by
   keywords. Keyword rules only decide what is worth sending to a model.
3. **The answer's shape is enforced by the provider.** Every AI call sends a JSON Schema and
   uses the provider's strict mode, so a malformed answer cannot come back.
4. **An incident is a thing that happened.** Articles are reports about incidents. A follow-up
   attaches to its incident; commentary attaches to nothing.
5. **Every stage says what it did.** Status is a list of facts (backlog size, brief age, which
   model labelled what), not one word.
6. **The scoring method does not change.** It was calibrated and argued over; the rebuild
   feeds it cleaner inputs.

## 4. How it runs

One workflow, started every hour by cron-job.org (GitHub's own scheduler was up to 7 hours late).

```
every hour
  1 collect   fetch feeds and GDELT, normalise, drop exact duplicates   -> article store
  2 label     send waiting articles to a model, 12 at a time            -> labels
  3 match     ask a model which known incident each report belongs to   -> incidents
  4 publish   write the small files the website reads

at the 04:00 and 13:00 UTC hours, additionally
  5 score     components E, M, A, L, gates, smoothing (method unchanged)
  6 brief     one short call per theatre
```

One workflow and one writer means the collector and the pipeline can no longer race each other
on the data branch. The incident list becomes fresh hourly; the index still moves twice a day,
because its smoothing and its "four runs before the level drops" rule are defined per run.

## 5. The AI layer

- **Providers:** Gemini and Groq, both free. A fixed, ordered model list per task, written in
  the config. No more "newest model of the family".
- **Strict output:** Groq `response_format: json_schema` with `strict: true` (documented as
  guaranteed for `openai/gpt-oss-120b` and `openai/gpt-oss-20b`, the models we already use).
  Gemini: a schema plus low thinking. Google's documentation now describes a newer endpoint
  than the one our code calls, so the exact Gemini request is confirmed by a live probe before
  anything is built on it (build step 0).
- **Budget counts answers, not attempts.** Rate-limit waits follow the provider's own
  "retry after" header.
- **Every label records its model.** The site can show how much each model did.
- **Tasks and their size** (Groq's limit is about 8,000 tokens a minute per model):

| Task | When | Size per call | Calls |
|---|---|---|---|
| Label 12 articles | hourly | about 2,900 in, up to 2,500 out | 1 to 3 an hour |
| Match reports to incidents | hourly | about 2,200 in, 300 out | 1 an hour |
| Assess a region | twice daily | about 5,300 in, 1,000 out | 2 per slot |
| Brief, one theatre | twice daily | about 3,000 in, 700 out | 6 per slot |

Estimated total: about 250,000 tokens a day. That fits the free allowances only if they are what
the public tables say. Adam needs to read his real limits from his Groq and Google AI Studio
consoles (section 13).

- **Summaries only where shown.** Irrelevant articles get a short answer with no summaries,
  which cuts output by roughly 40%.

## 6. Incidents

Each label now says what kind of report the article is:

- `new_incident`: reports something that happened (attack, attempt, disrupted plot, arrest,
  sabotage).
- `update`: more about an incident already reported (victims, motive, arrests after an attack,
  a trial).
- `context`: commentary, policy, analysis, warnings. Never an incident.
- `none`: not relevant.

For `new_incident` and `update` the label also states the underlying incident's facts: type,
severity, the date it happened (not the date of the article), country and place.

Matching is a second, small call: the model gets the report and a short list of incidents from
the last 30 days and must answer with one of their ids or "new". The list of allowed ids is part
of the schema, so it cannot invent one.

- A report matched to an incident is added to its timeline. The incident's severity is the
  highest its reports state, so a death toll that rises is picked up.
- An `update` with no match creates the incident it describes, dated when it happened.
- An article no model has matched yet is "waiting" and is not listed.
- `config/overrides.yaml` lets Adam merge two incidents, split one, or remove one by hand. The
  pipeline applies it every run and the site lists the corrections made.

Traced example: "The alleged Kraków shooter died in hospital" (2026-11-09). Today: a new row,
type "other", severity 0. Rebuild: labelled `update`, incident facts "attack, Kraków, PL,
2026-11-07"; the matcher returns the Kraków incident's id; it appears as the fourth line of
that incident's timeline and nowhere else.

## 7. The brief

One call per theatre (six), each with that theatre's 25 most relevant reports. Each returns one
or two lines, the top reports, the Slovak angle and any dated upcoming events. A theatre whose
call fails keeps its previous text with its real date shown. Nothing is marked "ok" when it is
old.

## 8. Scoring

Formulas, weights, gates, smoothing and thresholds are carried over unchanged, with their tests.
Differences in inputs only:

- E counts incidents (severity 1 or more), as before in effect, since severity 0 weighed 0.
- The incident date is when it happened.
- After migration the event history is recomputed once with the existing rescore tool, as after
  every change to what counts.

A continuity check compares the new index with the published one for the same days
(section 12).

## 9. Data files

The website stops downloading one 440 KB file with everything in it.

| File | Holds | Read by |
|---|---|---|
| `status.json` | each stage's result, backlog, brief age, source health | every page |
| `summary.json` | both regions: level, index, components, gates, drivers, official levels | home pages |
| `incidents/current.json` | incidents of the last 60 days with their timelines | incident list, map |
| `incidents/2026-11.json` | one file per month, kept | archive (later) |
| `reports.json` | relevant reports of the last 48 hours | latest reports, geopolitics map |
| `geopolitics.json` | theatres, brief, watchlist | geopolitics page |
| `history.json` | one row per region per scoring run | charts |

Internal state (article store, baselines, scoring state) lives beside them and the site never
reads it. The 28 full run snapshots (about 10 MB) are no longer kept, so the "view an older
run" picker goes away; the history chart and the monthly incident files replace it.

## 10. Status and alerts

- Each stage reports ok, degraded or failed, with the reason in words.
- The run is "ok" when: at least 10 press sources are fresh, no article has waited more than
  6 hours for a label, both regions were scored with a model assessment, and the brief is
  under 24 hours old.
- One GitHub issue at most. It opens after 24 hours of not-ok and closes itself on recovery.
- The site shows the same facts in plain words ("12 articles waiting for classification",
  "brief written yesterday 14:05").

## 11. What is rewritten and what is carried over

Rewritten from scratch: the AI layer, labelling, incident logic, the brief, status and alerts,
the data files, the workflows, and the parts of the website that read data.

Carried over with their tests, because the audit found no fault in them: the feed adapters,
URL and date normalisation, exact-duplicate removal, the place lookup, the official-level
readers, and the scoring formulas. Retyping tested fetch code would add risk and fix nothing.
If Adam wants these retyped as well, say so; it roughly doubles the work.

The old pipeline keeps running until the new one has proved itself, then it is deleted.

## 12. Build order

Each step ends with something that can be checked. One step at a time.

0. **Provider probe.** One manual workflow run: strict JSON on both Groq models and on Gemini,
   five real batches each, measuring valid answers and speed. Decides the model order.
1. **AI layer** with tests on recorded answers.
2. **Article store and hourly labelling** on a separate folder of the data branch.
3. **Incident matching**, replayed over the last three weeks of stored articles. Check: Kraków,
   the Italian school hoaxes and the Nvidia story each come out as one incident.
4. **Scoring port** and the continuity check against the published history.
5. **Brief per theatre.**
6. **Data files, status, alerts.**
7. **Website on the new files**, same look, with incident timelines.
8. **Seven days side by side** with the old pipeline, then switch over.

Acceptance, measured over the seven days:

- at least 95% of hourly runs finish, and at least 90% of scoring slots are "ok";
- no incident exists without a model label;
- 95% of articles are labelled within 3 hours;
- the brief is under 24 hours old on at least 6 of 7 days;
- in a hand-checked sample of 50 incidents, at most 2 are repeats of another;
- the index stays within 5 points of the old one on the same day, or the difference is explained.

## 13. Not verified yet

- Gemini's exact strict-JSON request on a free key (step 0 settles it).
- The real free-tier limits. The public Groq table is labelled as the Developer plan and gives
  30 requests a minute, 8,000 tokens a minute and 200,000 tokens a day per model; Google's page
  gives no numbers and points to AI Studio. Adam: please read both from your consoles.
- Whether hourly AI calls from GitHub's shared servers are refused more often than twice-daily
  ones. Step 2 measures it.
- The security review and the website review from the audit did not finish. The security
  review happens before switch-over, single-threaded.

## 13a. Step 0 results (probe run 43260605889, 2026-11-12 16:37 to 16:49 UTC)

The same 48 real articles, in 4 batches of 12, went to each model with strict JSON.

| Model | Valid answers | Labels | Time per batch | Matching test |
|---|---|---|---|---|
| Groq `openai/gpt-oss-120b` | 4 of 4 | 48 of 48 | 7 s | 4 of 4 |
| Gemini `gemini-3.6-flash` (minimal thinking) | 4 of 4 | 48 of 48 | 9 to 75 s | 4 of 4 |
| Groq `openai/gpt-oss-20b` | 3 of 4 | 31 of 48 | 4 s | 4 of 4 |
| Gemini `gemini-3.5-flash-lite` | 0 of 4 | 0 | refused (503) or timed out | 4 of 4 |
| Gemini `gemini-3.8-flash` | 0 of 4 | 0 | refused (503) every time | timed out |

Decisions:

- **Labelling order:** Groq 120b first, Gemini 3.6-flash second. The 20b model is not used for
  labelling (one answer cut off at the output limit, one refused, three self-contradicting
  labels); it stays as a fallback for the small matching call only.
- **Gemini request confirmed:** the current endpoint accepts `responseJsonSchema` together with
  `thinkingConfig.thinkingLevel`. Its timeout becomes 120 s: two of its four answers took over
  70 s, which the old 45 s timeout would have thrown away.
- **Batch size goes down from 12:** Groq 120b used up to 3,697 of its 4,096 output tokens on 12
  articles. Step 1 settles on 8 or 10.
- **Groq's real limits** (from its response headers): 1,000 requests a day and 8,000 tokens a
  minute per model. A daily token limit is not stated there.
- **Not shown:** whether strict mode fixes Gemini 3.8-flash, because Google refused every call
  to it during the run, including the old-style control. The same 3.6-flash model that broke
  7 answers without a schema in the morning run gave 5 valid answers of 5 with one.
- **Quality:** the two working models agreed on the kind of report for 34 of 48 articles and
  on the incident date for 46. Gemini recognises follow-ups better; Groq is stricter about
  what is an incident at all. Both read Slovak, Czech, Polish, Hungarian and German.
- **Open for step 3:** both models labelled shootings with no stated motive (police shot at
  in Kraków, a shooting near the White House) as "unrest" or "other". The prompt must say
  where an attack of unknown motive belongs; that is a method decision for Adam.

## 13b. What changed while building (2026-11-12, steps 1 to 6)

- **Strict mode is not a hard promise.** Groq refused about one answer in twenty with "the
  generated JSON does not match the schema" (HTTP 400). So section 3's "a malformed answer
  cannot come back" really means: the provider refuses it instead of handing it to us. The
  code asks the same model once more, then the next model; a batch that still fails waits for
  the next hour and the rest of the hour's batches are still tried.
- **Severity keeps the old scale.** A threat with no act (a bomb hoax) is listed as an
  incident with severity 0 and weighs nothing in the index, exactly as before. Without this
  the new labels would have counted every threat as 1 and raised the index.
- **The incident's day is the one most of its reports give.** The first report of the Kraków
  shooting was dated a day early by the model; the 18 that followed were right.
- **While the old pipeline runs, the new one reads what the old one collects** (the hourly
  buffer, the official levels, the media counts, the source health) and fetches nothing
  itself, so no news site or government page is visited twice. It writes only under `v2/` of
  the data branch.
- **Quiet hours.** In the old pipeline's two AI hours (04 and 13 UTC) the new one asks no model
  for labels, so it does not take free allowance from the pipeline that feeds the live site.
  Its own scoring runs an hour later (05 and 14 UTC) under the same slot names.
- **The index continues.** The first run takes over the old pipeline's history, scoring state
  and incidents (severity 1 or more). Checked on the stored data of 2026-11-12: the carried
  incidents give exactly the old index, level and components.
- **Alerts stay with the old pipeline** until switch-over; the new alert code is written and
  tested but not called, so there is no second stream of emails.

Left for switch-over day, on purpose:

1. Fetching for itself: the new run takes over the collector's fetch, the official-level
   readers and the media counts (the same carried-over code), and `quiet_hours` is emptied.
2. The security review of the new code.
3. The website switch (step 7 is built on branch `rebuild` and not deployed).
4. Deleting the old pipeline, its workflows and its files on the data branch.

## 14. Feature ideas

Chosen by Adam on 2026-11-12: incident timelines (built in step 7), then ideas 1, 2 and 6 once the
rebuild has switched over. Idea 13 (the badge): Adam chose to build it, against my advice,
so it is built with the website (step 7) on the new data files, with these safeguards: the
official SIS level comes first and ours beside it marked "neoficiálny odhad", it carries the
date, and it greys out when the data is more than 24 hours old. The rest are a backlog.

| # | Idea | For whom | Needs | Cost and risk |
|---|---|---|---|---|
| 1 | "Why this level": plain-words account of what moved the index this week | students, teachers | nothing new; computed from the components | low |
| 2 | Click a day on the chart to see that day's incidents | everyone | the monthly incident files | low |
| 3 | Neighbour cards: CZ, PL, HU, AT, UA with incidents, official level and travel advice | delegates, public | data already collected | low |
| 4 | Feeds to subscribe to: new incidents, and any change in an official level | analysts, journalists | two static feed files | low |
| 5 | Data download (CSV) of incidents and index history | MCS policy analysts, student research | static files, a licence line | low |
| 6 | Corrections log and accuracy page: what was fixed by hand, and a monthly spot check | anyone judging trust | the overrides file; an hour of Adam's time a month | low |
| 7 | Glossary in Slovak: NBAC, TE-SAT, hybrid threat, in a hover | students | written once | low |
| 8 | Archive and search past 60 days | analysts | the monthly files; a search box | medium |
| 9 | Hybrid threats indicator beside terrorism | public, analysts | its own method, baseline and calibration | high: a second number to defend |
| 10 | Weekly digest page in Slovak and English | delegates, teachers | one more AI task; Slovak quality checks | medium: AI prose under MCS's name |
| 11 | Briefing pack per theatre for Model UN preparation, printable | delegates | the brief and the watchlist | medium |
| 12 | Which outlets report first and are confirmed most often | media-literacy teaching | counts from the article store | medium: ranking named outlets invites complaints |
| 13 | Embeddable badge with today's level | schools, partners | a tiny page | I advise against: an unofficial level shown without its explanation |
