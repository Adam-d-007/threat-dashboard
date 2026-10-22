# How the dashboard indicator is computed

The dashboard shows its own terrorism threat level for Slovakia and for the EU on the Slovak
NBAC scale of 1 to 4, always next to the official level published by the Slovak Information
Service (SIS). **It is a dashboard indicator computed from open sources, not an official or
professional threat assessment.** The official SIS level is an input and a comparison point,
not a target the model tries to reproduce.

All numbers below live in [`pipeline/config/scoring.yaml`](../pipeline/config/scoring.yaml).
They are starting values from the build spec, to be reviewed after four weeks of live runs.

## The level and the index

Every run (twice a day) computes a **pressure** P between 0 and 1 for each region. It is shown
as an **index** from 0 to 100, and turned into a **level**:

| P | Level | Name |
|---|---|---|
| below 0.25 | 1 | Low |
| 0.25 to 0.50 | 2 | Elevated |
| 0.50 to 0.75 | 3 | High |
| 0.75 and above | 4 | Critical |

The NBAC definitions make level 2 almost permanent: it applies whenever a terrorist act is
probable or has happened anywhere in the EU or NATO, and Europol counted 45 attacks in 10 member
states in 2025. So the level rarely moves; **the index is the number that moves day to day**.

## The four components

P is a weighted sum of four components, each between 0 and 1:

| Component | Weight | What it measures |
|---|---|---|
| **E**, events | 35% | Terrorism-related incidents in the last 60 days |
| **M**, media | 15% | News coverage of terrorism mentioning the region |
| **A**, official levels | 20% | Official threat levels elsewhere and other governments' travel advice |
| **L**, language model | 30% | A language model's reading of the events against the NBAC definitions |

### A shared curve

E and M compare today with a normal level (a baseline). Both use the same curve, so a normal
day reads the same everywhere:

f(r) = 1 − 0.625^r, where r = today ÷ normal (capped at 5)

At the normal level f is 0.375 (the middle of level 2); at twice normal about 0.61 (level 3);
at three times about 0.76 (the edge of level 4).

### E, events

Each incident from the last 60 days counts as:

**severity weight × proximity × corroboration × e^(−age in days ÷ 10)**

- **Severity weight:** 1, 2, 4, 7 and 10 for severity 1 to 5 (an arrest is 1, an attack with 5
  or more deaths is 10), so one deadly attack outweighs several arrests.
- **Proximity, Slovakia:** 1.0 in Slovakia; 0.5 in Czechia, Austria, Hungary, Poland and
  Ukraine; 0.25 elsewhere in the EU; 0.7 outside the EU only with a direct Slovak link.
- **Proximity, EU:** 1.0 in a member state; 0.3 in the UK, EEA and candidate countries.
- **Corroboration:** 1.0 when two independent outlets or one official source report it; 0.6 for
  a single quality outlet; 0.3 for a single item seen only through GDELT.
- **Age:** an incident's weight halves about every 7 days.

The sum is compared with its median over the last 180 days. A floor (1.0 for Slovakia, 4.0 for
the EU) stops a near-empty baseline from turning one arrest into a spike.

### M, media

Articles that GDELT tags with its TERROR theme and that mention the region (Slovakia, or any EU
member state) on the latest complete day, against the median of the previous 90 complete days.
A day counts as complete when at least 90 of its 96 GDELT files were read. The median is never
taken below a floor: 8 articles for Slovakia, where GDELT tags very few (see the replays
below), and 1 for the EU. Media attention
measures coverage, not threat (a dramatic trial raises it), which is why its weight is only 15%.

### A, official levels

Each official level is turned into 0 to 1 on its own scale ((level − lowest) ÷ (highest −
lowest)); UK travel advice maps "cannot be ruled out" to 0, "likely" to 0.5 and "very likely"
to 1.

Travel advice comes from nine governments: the UK, the US, Canada, Germany and New Zealand for all
27 states, and the Netherlands, Japan, Czechia and Denmark for Slovakia only (their data is
published per country, and each source is read once per run). A government never rates its own
country. Other ministries were checked and left out: their sites forbid or block automated
reading, or build the page in the browser (see `pipeline/config/anchors.yaml`).

- **Slovakia:** SIS 40%, Poland 30%, the mean of all travel advice for Slovakia 30%. Austria
  publishes no level.
- **EU:** the mean of all travel advice across the 27 states (50%) and the mean of the published
  national levels of France, Belgium, the Netherlands and Poland (50%).
- **Rise bonus:** +0.15 when any of them rose in the last 30 days.

France's level is entered by hand, because every official French page with it blocks automated
reading; it is shown as stale after 180 days without a check.

### L, the language model

Once per region, a language model (Gemini, or Groq when Gemini is unavailable) receives the NBAC
level definitions, up to 40 events with their ids, the official levels, the E, M and A values and
the last three runs. It returns a level, a position within the level (low, mid or high), a
confidence, up to five drivers that must each cite events by id, and what changed. Drivers that
cite an id it was not given are dropped. It is told to judge only from the supplied events and
to return level 1 when the evidence is thin.

L = (level − 1 + position) ÷ 4, with position 0.17, 0.5 or 0.83.

### When a component has no value

A component without a value is left out, and the remaining weights are scaled up to sum to 1.
This happens when:

- **the language model fails** (the page says so), and
- **M is warming up.** It compares today with its own history, which only starts with the
  first live runs (22 October 2026). Until M has 14 complete days it is left out.

**The indicator is provisional for its first 14 days.** E normally compares today with the median
of 180 days. Until it has 14 distinct days of history, it uses the median of the days there are,
so on the first day it reads close to normal and gains meaning each day. The page shows the level
and index with a "provisional" label, a dashed border and the date the full method starts. This
is a compromise Adam asked for (2026-10-22): a first estimate is shown rather than none, but it
should be read as one. History is counted in days, not runs, so a burst of manual runs cannot
shorten the provisional period. Two other choices were rejected: comparing E with its floor
would have read six ordinary events as seven times normal (EU level 3 on the first day), and
leaving E out made the score rest on official levels and the language model alone.

If no component has a value at all, the page shows no level, rather than an invented one.

## Gates from the NBAC definitions

Gates bound which levels P may reach. Each gate that applies is listed on the page with the
events behind it.

| Gate | Region | Rule |
|---|---|---|
| Floor 2 | Both | A corroborated attack or attempt of severity 2+ in an EU or NATO state in the last 30 days sets the level to at least 2 |
| Cap at 2 | Slovakia | Level 3 needs a corroborated event with a direct Slovak link in 30 days, or a corroborated attack of severity 3+ in the EU or NATO in 14 days with at least an indirect Slovak link |
| Cap at 3 | Slovakia | Level 4 needs a corroborated direct-link attack, attempt or disrupted plot within 72 hours with at least one official source |
| Cap at 3 | EU | Level 4 needs a severity 5 attack in the EU in 7 days, or 3 attacks of severity 3+ in at least 2 member states in 7 days |

The floor is listed whenever it holds; a cap only when it actually held the level down. The
official SIS level is **not** a floor: the indicator may sit below or above it.

## Rules level and disagreement

The **rules level** is the level from E, M and A alone, with the gates applied. When the language
model's level differs from it by 2 or more, or by 1 when either is 3 or higher, the run is marked
as a disagreement, the final level is the gated rules level, and the page shows both. The
language model can move the index, but it cannot move the level against the rules on its own.

## Smoothing and hysteresis

- **Index:** the displayed index is a moving average over runs (half the new value, half the
  previous), so it does not jump with every run.
- **Up:** the level goes up as soon as P crosses a threshold that the gates allow.
- **Down:** the level goes down only after 4 runs in a row (48 hours) with P at least 0.03 below
  the threshold. A gate can still force it down at once: when the event that lifted a cap leaves
  its window, the cap applies immediately, because the NBAC definition no longer supports the
  higher level.

## Where the build differs from the spec

| Spec | Build | Why |
|---|---|---|
| Raw index shown only when a gate raises the level | Also whenever the level rises | Otherwise one run showed level 3 with index 48, outside level 3's band |
| 180-day backfill sets the E and M baselines | E and M warm up from live data | A backfill from GDELT bulk files would measure something different from the live event signal |
| Replays from GDELT bulk data | Incidents rebuilt for E, real GDELT bulk counts for M (below) | E is built from classified news items, which bulk files do not contain; M is replayed from one GKG file per hour, not all four |
| Media baselines from GDELT DOC TimelineVolRaw | GKG theme counts read from the bulk files every run | One source for live counts, baselines and replays; DOC calls are rate-limited from GitHub |
| Austria in the Slovak anchors | Left out | DSN publishes no current level |

## Calibration so far

Replays rebuild each incident as the pipeline would have recorded it (date, country, deaths,
Slovak link, corroboration), on top of 30 days of quiet history (an arrest somewhere in the EU
every four days, one attack in France). They run without the language model and media
components, so they test the events, official levels, gates and smoothing, not the full model.

| Window | Slovakia: level/index before → first run after | EU: same | Gates |
|---|---|---|---|
| Quiet 30 days | level 2, index 30 | level 2, index 44 | floor 2 |
| Bratislava, 12 Oct 2022 (2 killed, Slovakia) | 2/30 → 3/66 | 2/44 → 3/67 | Slovak cap at 2 lifted |
| Vienna, 2 Nov 2020 (4 killed, neighbour) | 2/30 → 3/64 | 2/44 → 3/67 | Slovak cap at 2 lifted |
| Solingen, 23 Aug 2024 (3 killed, no Slovak link) | 2/30 → 2/42 | 2/44 → 3/67 | Slovak cap at 2 holds the level |
| Villach, 15 Feb 2025 (1 killed, neighbour) | 2/30 → 3/64 | 2/44 → 3/67 | Slovak cap at 2 lifted |

Every replay raises the index within one run. The quiet month keeps Slovakia at level 2 with an
index of 30, the bottom of the spec's 30 to 45 target.

### Replays with real media counts

`pipeline/tools/gkg_replay.py` read GDELT GKG bulk files from 15 days before each attack to 2 days
after: one file per hour (the first that exists in the hour, 24 of the 96 a day), about 2.5 GB per incident, counted in
memory. Only the daily counts are kept, in `pipeline/data/replays/`, scaled by 4 to a full day.
The test `test_bulk_replays_count_real_media_and_still_raise_the_index` then replays each
incident with E from the rebuilt incident and M from these counts (no language model). The
table shows level/index in the last run before the attack and the first run after, and M before
against its highest value in the two days after, with the Slovak floor at 8 (below).

| Window | Slovakia | EU |
|---|---|---|
| Bratislava, 12 Oct 2022 | 2/24 → 3/52, M 0.00 → max 0.88 | 2/44 → 3/63, M 0.50 → max 0.52 |
| Vienna, 2 Nov 2020 | 2/30 → 3/64, no M (see below) | 2/44 → 3/67, no M |
| Solingen, 23 Aug 2024 | 2/31 → 2/40, M 0.38 → max 0.38 | 2/44 → 3/63, M 0.51 → max 0.60 |
| Villach, 15 Feb 2025 | 2/29 → 3/55, M 0.21 → max 0.21 | 2/44 → 3/64, M 0.54 → max 0.54 |

What the real counts show:

- **GDELT's 2020 archive has gaps.** Around the Vienna attack 178 of 432 hours have no GKG file
  at all, and no day reaches the 90 of 96 files the live pipeline needs to count it. M therefore
  has no value in the Vienna replay, exactly as it would have had live.

- **EU coverage moves little.** The EU's TERROR count is in the thousands every day, so one
  attack raises it by half at most (Solingen: ratio 1.96, two days later). Villach came two
  days after the Munich car attack, which had already raised the baseline.
- **Slovak coverage is tiny and noisy, hence the floor of 8.** The median day in each window
  had no Slovak TERROR article in the sample. With the floor at 1 (the first setting), four
  stray articles gave M = 0.85 before Solingen and Villach, Bratislava's real rise (to 36
  articles two days after) barely showed (0.85 to 0.90), and the quiet Slovak index rose from
  30 to 36. With the floor at 8 (set on 2026-10-22): the quiet index is 29 to 31;
  Bratislava's M climbs 0, 0.21, 0.61, 0.88 over two days; Solingen, with no Slovak link,
  keeps Slovakia at level 2 with M at most 0.38.

**Open questions for the four-week review:**

- A single deadly attack anywhere in the EU lifts the EU to level 3. Is that the intended
  reading of NBAC level 3 ("a terrorist act committed in an EU or NATO state that may affect
  security")?
- Ukraine sits at proximity 0.5 for Slovakia. Acts of war are classified as geopolitics, not
  terrorism, so they should not inflate the index; this needs checking on live data.
- The weights (35/15/20/30) are judgement calls and are reviewed with four weeks of data.
- The Slovak media floor of 8 was set from four replays; check it against live counts, which
  read all 96 files a day rather than one an hour.
