import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Lang = "en" | "sk";

const en = {
  siteName: "Threat monitor",
  nav: {
    geopolitics: "Geopolitics",
    terrorism: "Terrorism",
    sources: "Sources",
    method: "Method",
  },
  region: { SK: "Slovakia", EU: "EU-27" },
  heroTitle: {
    SK: "Monitoring current terrorist threats in Slovakia",
    EU: "Monitoring current terrorist threats in the EU",
  },
  geoTitle: "Geopolitical developments relevant to Slovakia and the EU",
  levelNames: ["Low", "Elevated", "High", "Critical"] as string[],
  levelWord: "Level",
  indicator: "Dashboard indicator",
  indicatorNote:
    "Computed from open sources. The level rarely moves; the index (0 to 100) shows day-to-day pressure.",
  official: "Official level",
  officialSince: (d: string) => `since ${d}`,
  officialSource: "Slovak Information Service (SIS), NBAC",
  officialMissing: "The official level could not be read in this run.",
  noEuLevel: "No EU-wide official level exists. Member-state levels are shown below.",
  index: "Index",
  changeSinceLast: (d: number) => `${d > 0 ? "+" : ""}${d} since last run`,
  noChange: "index unchanged since last run",
  newSinceLast: (n: number) => `${n} new incident${n === 1 ? "" : "s"}`,
  mapFull: "Full screen",
  mapExit: "Close",
  anchors: "Official levels elsewhere",
  anchorsExplain:
    "Threat levels that other countries declare for their own territory. 2/4 means the second of four steps, where 1 is the lowest. Click one to open the official page.",
  travelAdvice: (n: number) => `Travel advice from ${n} ${n === 1 ? "government" : "governments"}`,
  travelExplainSK:
    "How other governments rate security for their citizens travelling to Slovakia: an independent second opinion. The first step of each scale (e.g. Level 1, groen) means normal precautions. Together they make up 30% of the official levels component. Click one to open that government's page.",
  travelExplainEU:
    "How other governments rate security for travel to each of the 27 member states, counted per level. Together they make up half of the official levels component. Open a chip for the list of countries and their pages.",
  chipTitle: (name: string, raw: string, level: number, n: number) =>
    `${name}: ${raw}, step ${level} of ${n} (1 is the lowest). Opens the official page.`,
  notComputedTitle: "The indicator is not computed yet",
  provisional: "Provisional",
  provisionalNote: (d: string) =>
    `Provisional until ${d}: events are compared with the few days of history collected so far (news coverage already has its 90 days). Read it as a first estimate; from ${d} it is measured against two weeks of history.`,
  notComputedBody:
    "Scoring is still being built. Until it runs, this page shows the official level and the latest reports only, never an estimate.",
  sampleBanner:
    "SAMPLE DATA. Everything on this page is made up for design work and means nothing.",
  banners: {
    disagreement:
      "The language model reads the situation differently from the rules (two levels apart, or one level at level 3 or above). In that case the rules decide the level and index shown. This is not an error.",
    llmFallback: "The language model was unavailable. This run uses rules only.",
    sourcesFailing: (n: number) => `${n} source${n === 1 ? "" : "s"} failed in this run.`,
  },
  gateNames: {
    floor_eu_attack_30d: "It cannot fall below 2: a confirmed attack happened in an EU or NATO state in the last 30 days.",
    cap_sk_2: "It cannot rise above 2: no recent incident is directly linked to Slovakia.",
    cap_sk_3: "It cannot rise above 3: no official source has confirmed an imminent threat to Slovakia.",
    cap_eu_3: "It cannot rise above 3: there was no mass-casualty attack or series of attacks in the last 7 days.",
  } as Record<string, string>,
  history: "Index history",
  ranges: { "30": "30 days", "90": "90 days", "365": "1 year", all: "All" } as Record<string, string>,
  officialLine: "Official level",
  components: "What makes up the index",
  componentNames: {
    events: "Events",
    media: "Media attention",
    anchors: "Official levels",
    llm: "Model assessment",
  } as Record<string, string>,
  componentHelp: {
    events:
      "Corroborated incidents in the last 60 days, weighted by severity, distance and age, against their 180-day median.",
    media: "Articles on terrorism mentioning the region in 24 h, against their 90-day median.",
    anchors: "Official threat levels and other governments' travel advice, normalised to 0 to 1.",
    llm: "A language model's reading of the events against the NBAC level definitions.",
  } as Record<string, string>,
  weight: "weight",
  value: "value",
  componentStatus: {
    warming_up: "warming up: builds its normal level from the first weeks of data",
    disabled: "language model not used in this run",
    fallback: "language model unavailable: left out of this run",
    no_data: "no data in this run",
  } as Record<string, string>,
  points: "points",
  inputs: "Inputs",
  basedOn: "Based on",
  assessment: "Assessment",
  whatChanged: "What changed",
  confidence: "Confidence",
  confidenceNames: { low: "low", medium: "medium", high: "high" } as Record<string, string>,
  model: "Model",
  changes: "Changes since the last run",
  newEvents: "New events",
  anchorChanges: "Official level changes",
  sourceChanges: "Source status changes",
  nothingChanged: "Nothing changed.",
  map: "Incident map, last 30 days",
  table: "Incidents",
  tableCols: {
    date: "Date",
    place: "Place",
    type: "Type",
    ideology: "Ideology",
    severity: "Severity",
    sources: "Sources",
    corroborated: "Corroborated",
  },
  yes: "yes",
  no: "no",
  corroboratedOnly: "Corroborated only",
  allTypes: "All types",
  allIdeologies: "All ideologies",
  minSeverity: "Minimum severity",
  noEvents: "No events in this period.",
  eventTypes: {
    attack: "Attack",
    attempted_attack: "Attempted attack",
    plot_disrupted: "Plot disrupted",
    arrest: "Arrest",
    conviction: "Conviction",
    threat_statement: "Threat statement",
    sabotage: "Sabotage",
    other: "Other",
  } as Record<string, string>,
  ideologies: {
    jihadist: "Jihadist",
    right_wing: "Right-wing",
    left_anarchist: "Left-wing and anarchist",
    ethno_separatist: "Ethno-nationalist and separatist",
    state_linked: "State-linked",
    other: "Other",
    unknown: "Unknown",
  } as Record<string, string>,
  ideologyMix: "Ideology mix, last 90 days, beside Europol TE-SAT",
  mix: {
    label: "Compare",
    attacks: "Attacks",
    arrests: "Arrests",
    ours: (n: number) => `This dashboard, last 90 days (${n})`,
    theirs: (report: number, year: number, n: number) => `TE-SAT ${report}, EU ${year} (${n})`,
    notInTesat: "not a TE-SAT category",
    note: "Shares of each total, not counts: 90 days of reports in this region against a full year of the whole EU. Attacks here are attacks, attempted attacks and disrupted plots; TE-SAT counts completed, failed and foiled attacks.",
  },
  baseRates: "Base rates",
  sisAnnual: {
    title: "Slovak Information Service: annual report",
    source: (year: number, published: string) => `SIS annual report for ${year} (published ${published})`,
    note: "Summarised by this dashboard; the latest report SIS has published.",
  },
  baseRatesPending:
    "Europol TE-SAT yearly figures and GTD history (which ends in 2021) will appear here once they are entered.",
  tesat: {
    source: (report: number, year: number) => `Europol TE-SAT ${report}, figures for ${year}, EU Member States`,
    attacks: "terrorist attacks",
    split: (c: number, f: number, fo: number) => `${c} completed · ${f} failed · ${fo} foiled`,
    arrests: "arrests",
    deaths: "deaths",
    previous: (year: number, attacks: number, arrests: number) => `${year}: ${attacks} attacks, ${arrests} arrests`,
    byType: "Attacks by type",
    slovakia: (attacks: number, arrests: number) =>
      `Slovakia reported ${attacks} attacks and ${arrests} arrests for terrorism in that year.`,
    gtdPending: "Long-term history from the Global Terrorism Database (which ends in 2021) will be added later.",
  },
  gtd: {
    sk: "Slovakia",
    eu: "the EU-27",
    title: (where: string) => `Terrorist incidents per year in ${where}`,
    summary: (total: number, shown: string, year: number, n: number) =>
      `${shown} ${total === 1 ? "incident" : "incidents"} in all; most in ${year} (${n})`,
    bar: (year: number, n: number, deaths: number) => `${year}: ${n} incidents, ${deaths} deaths`,
    noData: (year: number) => `${year}: no data`,
    missing: (years: string) => `No data for ${years}: START lost those records (dashed gap, not zero).`,
    ends: (year: number) =>
      `GTD data ends in ${year}. Yearly counts made by this dashboard: today's 27 member states for every year, failed attacks included, Czechoslovakia counted for the EU only, Slovakia from 1993 (method in pipeline/tools/gtd_aggregates.py).`,
  },
  latestReports: "Latest reports",
  dateEstimated: "date estimated",
  brief: "Daily brief",
  briefWritten: (when: string) => `Written ${when}: no language model could write a new one in the latest update.`,
  theatres: "Theatres",
  geoMap: {
    title: "Map of reports",
    pick: "Theatre",
    all: "All theatres",
    count: (n: number) => (n === 1 ? "1 report with a place" : `${n} reports with a place`),
    note: "Each circle is a place named in a report from this run. Terrorism reports are on the terrorism pages. A report belongs to every theatre whose countries it names.",
  },
  activity: "Activity versus normal",
  activityLow: "below normal",
  activityNormal: "normal",
  activityHigh: "above normal",
  tone: "Tone",
  topDevelopments: "Top developments",
  slovakAngle: "Slovak angle",
  watchlist: "Watchlist",
  unverified: "from news, unverified",
  geoNotComputed:
    "Theatre activity needs 90 days of collected history before it can be compared with normal. Until then this page lists the latest reports.",
  sources: {
    title: "Sources",
    intro: "Every source the pipeline reads, with its status in the latest run.",
    cols: {
      name: "Source",
      tier: "Tier",
      status: "Status",
      lastSuccess: "Last success",
      items: "Items",
      error: "Error",
    },
    tierHelp:
      "Tier A: official body. Tier B: wire service, quality outlet or research institute. Tier C: only seen through GDELT.",
  },
  sourceStatus: { ok: "ok", stale: "stale", failed: "failed", disabled: "disabled" } as Record<string, string>,
  never: "never",
  method: {
    title: "Method",
    body: [
      "Each region gets a composite pressure between 0 and 1, shown as an index from 0 to 100, and a level from 1 to 4 on the Slovak NBAC scale.",
      "Four components feed the index: events (35%), media attention (15%), official levels in other countries (20%) and a language model's assessment (30%). Rules written from the NBAC definitions then limit which levels the index may reach; each rule that fires is shown on the page with the events behind it.",
      "Media volume is always compared with a rolling baseline, never shown as raw counts. Every number links to its inputs and the reports that produced it.",
      "The level shown is a dashboard indicator. It is not an official or professional threat assessment, and it is always shown next to the official SIS level.",
    ],
  },
  lastRun: "Updated",
  runPicker: "Run",
  latest: "latest",
  viewingOld: (id: string) => `You are viewing an earlier run (${id}).`,
  backToLatest: "Back to the latest run",
  gateMarker: "a rule changed the level",
  fullMethod: "Full method (in English)",
  hoursAgo: (h: number) => (h < 1 ? "just now" : `${h} h ago`),
  ageAmber: "The data is more than 10 hours old.",
  ageRed: "The data is more than 14 hours old: a scheduled run was probably missed.",
  loading: "Loading data…",
  loadError: "Could not load the data.",
  unsupported: (v: string) =>
    `The data file has version ${v}, which this page does not support. Please reload the page. If the problem continues, the site needs an update.`,
  theme: { dark: "Dark", light: "Light" },
  footer: "Dashboard indicator computed from open sources. Not an official threat assessment.",
  attribution:
    "Map data © OpenStreetMap contributors. Place names from GeoNames (CC BY 4.0). Media counts from the GDELT Project. Base rates from Europol TE-SAT and START's Global Terrorism Database.",
};

export type Strings = typeof en;

// Typed as Strings so a missing Slovak string is a compile error.
const sk: Strings = {
  siteName: "Monitor hrozieb",
  nav: {
    geopolitics: "Geopolitika",
    terrorism: "Terorizmus",
    sources: "Zdroje",
    method: "Metodika",
  },
  region: { SK: "Slovensko", EU: "EÚ-27" },
  heroTitle: {
    SK: "Monitoring aktuálnych hrozieb terorizmu na Slovensku",
    EU: "Monitoring aktuálnych hrozieb terorizmu v EÚ",
  },
  geoTitle: "Geopolitický vývoj dôležitý pre Slovensko a EÚ",
  // SIS wording: NÍZKY / ZVÝŠENÝ / VYSOKÝ / KRITICKÝ STUPEŇ OHROZENIA
  levelNames: ["Nízky", "Zvýšený", "Vysoký", "Kritický"],
  levelWord: "Stupeň",
  indicator: "Ukazovateľ dashboardu",
  indicatorNote:
    "Vypočítaný z otvorených zdrojov. Úroveň sa mení zriedka; index (0 až 100) ukazuje každodenný tlak.",
  official: "Oficiálna úroveň",
  officialSince: (d: string) => `od ${d}`,
  officialSource: "Slovenská informačná služba (SIS), NBAC",
  officialMissing: "Oficiálnu úroveň sa v tejto aktualizácii nepodarilo načítať.",
  noEuLevel: "Celoeurópska oficiálna úroveň neexistuje. Nižšie sú úrovne jednotlivých členských štátov.",
  index: "Index",
  changeSinceLast: (d: number) => `${d > 0 ? "+" : ""}${d} od poslednej aktualizácie`,
  noChange: "index bez zmeny od poslednej aktualizácie",
  newSinceLast: (n: number) =>
    n === 1 ? "1 nový incident" : n < 5 ? `${n} nové incidenty` : `${n} nových incidentov`,
  mapFull: "Celá obrazovka",
  mapExit: "Zavrieť",
  anchors: "Oficiálne úrovne v iných krajinách",
  anchorsExplain:
    "Stupne ohrozenia, ktoré iné štáty vyhlasujú pre svoje územie. Údaj 2/4 znamená druhý zo štyroch stupňov, pričom 1 je najnižší. Kliknutím otvoríte oficiálnu stránku.",
  travelAdvice: (n: number) => `Cestovné odporúčania ${n} ${n === 1 ? "vlády" : "vlád"}`,
  travelExplainSK:
    "Ako iné vlády hodnotia bezpečnosť pre svojich občanov cestujúcich na Slovensko: nezávislý druhý názor. Prvý stupeň každej stupnice (napr. Level 1, groen) znamená bežnú opatrnosť. Spolu tvoria 30 % zložky oficiálnych úrovní. Kliknutím otvoríte stránku danej vlády.",
  travelExplainEU:
    "Ako iné vlády hodnotia bezpečnosť pri cestách do jednotlivých 27 členských štátov, spočítané podľa stupňa. Spolu tvoria polovicu zložky oficiálnych úrovní. Po rozbalení uvidíte zoznam krajín s odkazmi.",
  chipTitle: (name: string, raw: string, level: number, n: number) =>
    `${name}: ${raw}, stupeň ${level} z ${n} (1 je najnižší). Otvorí oficiálnu stránku.`,
  notComputedTitle: "Ukazovateľ sa zatiaľ nepočíta",
  provisional: "Predbežný",
  provisionalNote: (d: string) =>
    `Predbežný do ${d}: udalosti porovnávame s niekoľkými dňami histórie, ktoré máme zatiaľ k dispozícii (mediálne pokrytie už má svojich 90 dní). Berte ho ako prvý odhad; od ${d} sa meria voči dvom týždňom histórie.`,
  notComputedBody:
    "Hodnotenie je ešte vo vývoji. Kým nebude spustené, táto stránka zobrazuje len oficiálnu úroveň a najnovšie správy, nikdy odhad.",
  sampleBanner:
    "UKÁŽKOVÉ ÚDAJE. Všetko na tejto stránke je vymyslené pre potreby návrhu a nemá žiadny význam.",
  banners: {
    disagreement:
      "Jazykový model hodnotí situáciu inak než pravidlá (o dva stupne, alebo o jeden pri stupni 3 a vyššom). V takom prípade o zobrazenej úrovni aj indexe rozhodujú pravidlá. Nejde o chybu.",
    llmFallback: "Jazykový model nebol dostupný. Táto aktualizácia používa len pravidlá.",
    sourcesFailing: (n: number) =>
      n === 1
        ? "V tejto aktualizácii zlyhal 1 zdroj."
        : `Počet zdrojov, ktoré v tejto aktualizácii zlyhali: ${n}.`,
  },
  gateNames: {
    floor_eu_attack_30d: "Nemôže klesnúť pod 2: za posledných 30 dní bol v štáte EÚ alebo NATO potvrdený útok.",
    cap_sk_2: "Nemôže stúpnuť nad 2: žiadny nedávny incident nie je priamo spojený so Slovenskom.",
    cap_sk_3: "Nemôže stúpnuť nad 3: žiadny oficiálny zdroj nepotvrdil bezprostrednú hrozbu pre Slovensko.",
    cap_eu_3: "Nemôže stúpnuť nad 3: za posledných 7 dní nedošlo k útoku s hromadnými obeťami ani k sérii útokov.",
  },
  history: "Vývoj indexu",
  ranges: { "30": "30 dní", "90": "90 dní", "365": "1 rok", all: "Všetko" },
  officialLine: "Oficiálna úroveň",
  components: "Z čoho sa skladá index",
  componentNames: {
    events: "Udalosti",
    media: "Mediálna pozornosť",
    anchors: "Oficiálne úrovne",
    llm: "Hodnotenie modelu",
  },
  componentHelp: {
    events:
      "Potvrdené incidenty za posledných 60 dní, vážené závažnosťou, vzdialenosťou a vekom, v porovnaní so 180-dňovým mediánom.",
    media: "Články o terorizme, ktoré spomínajú región, za 24 hodín v porovnaní s 90-dňovým mediánom.",
    anchors:
      "Oficiálne úrovne ohrozenia a cestovné odporúčania iných vlád, prepočítané na stupnicu 0 až 1.",
    llm: "Hodnotenie udalostí jazykovým modelom podľa definícií úrovní NBAC.",
  },
  weight: "váha",
  value: "hodnota",
  componentStatus: {
    warming_up: "zbiera sa história: bežnú úroveň si vytvára z prvých týždňov údajov",
    disabled: "jazykový model sa v tejto aktualizácii nepoužil",
    fallback: "jazykový model nebol dostupný: v tejto aktualizácii sa nezapočítal",
    no_data: "v tejto aktualizácii bez údajov",
  },
  points: "bodov",
  inputs: "Vstupy",
  basedOn: "Na základe",
  assessment: "Hodnotenie",
  whatChanged: "Čo sa zmenilo",
  confidence: "Istota",
  confidenceNames: { low: "nízka", medium: "stredná", high: "vysoká" },
  model: "Model",
  changes: "Zmeny od poslednej aktualizácie",
  newEvents: "Nové udalosti",
  anchorChanges: "Zmeny oficiálnych úrovní",
  sourceChanges: "Zmeny stavu zdrojov",
  nothingChanged: "Nič sa nezmenilo.",
  map: "Mapa incidentov za posledných 30 dní",
  table: "Incidenty",
  tableCols: {
    date: "Dátum",
    place: "Miesto",
    type: "Typ",
    ideology: "Ideológia",
    severity: "Závažnosť",
    sources: "Zdroje",
    corroborated: "Potvrdené",
  },
  yes: "áno",
  no: "nie",
  corroboratedOnly: "Len potvrdené",
  allTypes: "Všetky typy",
  allIdeologies: "Všetky ideológie",
  minSeverity: "Minimálna závažnosť",
  noEvents: "V tomto období nie sú žiadne udalosti.",
  eventTypes: {
    attack: "Útok",
    attempted_attack: "Pokus o útok",
    plot_disrupted: "Prekazený plán",
    arrest: "Zadržanie",
    conviction: "Odsúdenie",
    threat_statement: "Vyhrážka",
    sabotage: "Sabotáž",
    other: "Iné",
  },
  ideologies: {
    jihadist: "Džihádistický",
    right_wing: "Pravicový",
    left_anarchist: "Ľavicový a anarchistický",
    ethno_separatist: "Etnonacionalistický a separatistický",
    state_linked: "Napojený na štát",
    other: "Iný",
    unknown: "Neznámy",
  },
  ideologyMix: "Ideologické zloženie za posledných 90 dní v porovnaní s Europol TE-SAT",
  mix: {
    label: "Porovnať",
    attacks: "Útoky",
    arrests: "Zatknutia",
    ours: (n: number) => `Tento prehľad, posledných 90 dní (${n})`,
    theirs: (report: number, year: number, n: number) => `TE-SAT ${report}, EÚ ${year} (${n})`,
    notInTesat: "TE-SAT túto kategóriu nevedie",
    note: "Podiely z celku, nie počty: 90 dní správ z tohto regiónu oproti celému roku za celú EÚ. Útoky sú tu útoky, pokusy o útok a zmarené plány; TE-SAT počíta dokonané, neúspešné a zmarené útoky.",
  },
  baseRates: "Dlhodobé počty",
  sisAnnual: {
    title: "Slovenská informačná služba: výročná správa",
    source: (year: number, published: string) => `Správa o činnosti SIS za rok ${year} (zverejnená ${published})`,
    note: "Zhrnutie pripravil tento prehľad; ide o najnovšiu správu, ktorú SIS zverejnila.",
  },
  baseRatesPending:
    "Ročné údaje Europolu (TE-SAT) a historické údaje GTD (končia rokom 2021) sa tu zobrazia po ich doplnení.",
  tesat: {
    source: (report: number, year: number) => `Europol TE-SAT ${report}, údaje za rok ${year}, členské štáty EÚ`,
    attacks: "teroristických útokov",
    split: (c: number, f: number, fo: number) => `${c} dokonaných · ${f} neúspešných · ${fo} prekazených`,
    arrests: "zadržaných",
    deaths: "obetí",
    previous: (year: number, attacks: number, arrests: number) => `${year}: ${attacks} útokov, ${arrests} zadržaných`,
    byType: "Útoky podľa typu",
    slovakia: (attacks: number, arrests: number) =>
      `Slovensko v danom roku nahlásilo ${attacks} útokov a ${arrests} zadržaní za terorizmus.`,
    gtdPending: "Dlhodobá história z Global Terrorism Database (končí rokom 2021) bude doplnená neskôr.",
  },
  gtd: {
    sk: "na Slovensku",
    eu: "v EÚ-27",
    title: (where: string) => `Teroristické incidenty podľa rokov ${where}`,
    summary: (total: number, shown: string, year: number, n: number) =>
      `Spolu ${shown} ${total === 1 ? "incident" : total >= 2 && total <= 4 ? "incidenty" : "incidentov"}; najviac v roku ${year} (${n})`,
    bar: (year: number, n: number, deaths: number) => `${year}: ${n} incidentov, ${deaths} obetí`,
    noData: (year: number) => `${year}: bez údajov`,
    missing: (years: string) => `Za rok ${years} údaje chýbajú: START tieto záznamy stratil (prerušovaný rámik, nie nula).`,
    ends: (year: number) =>
      `Údaje GTD končia rokom ${year}. Ročné súčty pripravil tento prehľad: pre každý rok súčasných 27 členských štátov, vrátane neúspešných útokov, Česko-Slovensko len v súčte za EÚ, Slovensko od roku 1993 (postup v pipeline/tools/gtd_aggregates.py).`,
  },
  latestReports: "Najnovšie správy",
  dateEstimated: "dátum je odhadnutý",
  brief: "Denný prehľad",
  briefWritten: (when: string) => `Napísaný ${when}: pri poslednej aktualizácii nový prehľad nemohol vzniknúť.`,
  theatres: "Oblasti",
  geoMap: {
    title: "Mapa správ",
    pick: "Oblasť",
    all: "Všetky oblasti",
    count: (n: number) => (n === 1 ? "1 správa s miestom" : n >= 2 && n <= 4 ? `${n} správy s miestom` : `${n} správ s miestom`),
    note: "Každý kruh je miesto uvedené v správe z tohto behu. Správy o terorizme sú na stránkach o terorizme. Správa patrí do každej oblasti, ktorej krajinu uvádza.",
  },
  activity: "Aktivita oproti bežnému stavu",
  activityLow: "pod bežnou úrovňou",
  activityNormal: "bežná úroveň",
  activityHigh: "nad bežnou úrovňou",
  tone: "Tón",
  topDevelopments: "Najdôležitejší vývoj",
  slovakAngle: "Slovenský rozmer",
  watchlist: "Sledované termíny",
  unverified: "zo správ, neoverené",
  geoNotComputed:
    "Na porovnanie aktivity s bežným stavom treba 90 dní zozbieranej histórie. Dovtedy táto stránka zobrazuje najnovšie správy.",
  sources: {
    title: "Zdroje",
    intro: "Všetky zdroje, ktoré systém číta, a ich stav pri poslednej aktualizácii.",
    cols: {
      name: "Zdroj",
      tier: "Úroveň",
      status: "Stav",
      lastSuccess: "Posledný úspech",
      items: "Položky",
      error: "Chyba",
    },
    tierHelp:
      "Úroveň A: oficiálny orgán. Úroveň B: tlačová agentúra, kvalitné médium alebo výskumný ústav. Úroveň C: len cez GDELT.",
  },
  sourceStatus: { ok: "v poriadku", stale: "neaktuálny", failed: "zlyhal", disabled: "vypnutý" },
  never: "nikdy",
  method: {
    title: "Metodika",
    body: [
      "Každý región dostane súhrnný tlak od 0 do 1, zobrazený ako index od 0 do 100, a úroveň od 1 do 4 na slovenskej stupnici NBAC.",
      "Index tvoria štyri zložky: udalosti (35 %), mediálna pozornosť (15 %), oficiálne úrovne v iných krajinách (20 %) a hodnotenie jazykového modelu (30 %). Pravidlá odvodené z definícií NBAC potom obmedzujú, ktoré úrovne môže index dosiahnuť; každé uplatnené pravidlo sa zobrazí aj s udalosťami, ktoré ho spustili.",
      "Objem medializácie sa vždy porovnáva s kĺzavým základom, nikdy sa nezobrazuje ako absolútny počet. Každé číslo odkazuje na svoje vstupy a správy, z ktorých vzniklo.",
      "Zobrazená úroveň je ukazovateľ dashboardu. Nejde o oficiálne ani odborné hodnotenie hrozby a vždy sa zobrazuje vedľa oficiálnej úrovne SIS.",
    ],
  },
  lastRun: "Aktualizované",
  runPicker: "Aktualizácia",
  latest: "najnovšia",
  viewingOld: (id: string) => `Prezeráte staršiu aktualizáciu (${id}).`,
  backToLatest: "Späť na najnovšiu",
  gateMarker: "pravidlo zmenilo úroveň",
  fullMethod: "Podrobná metodika (v angličtine)",
  hoursAgo: (h: number) => (h < 1 ? "práve teraz" : `pred ${h} h`),
  ageAmber: "Údaje sú staršie ako 10 hodín.",
  ageRed: "Údaje sú staršie ako 14 hodín: plánovaná aktualizácia pravdepodobne neprebehla.",
  loading: "Načítavajú sa údaje…",
  loadError: "Údaje sa nepodarilo načítať.",
  unsupported: (v: string) =>
    `Súbor s údajmi má verziu ${v}, ktorú táto stránka nepodporuje. Obnovte, prosím, stránku. Ak problém pretrváva, stránku je potrebné aktualizovať.`,
  theme: { dark: "Tmavý", light: "Svetlý" },
  footer: "Ukazovateľ dashboardu vypočítaný z otvorených zdrojov. Nejde o oficiálne hodnotenie hrozby.",
  attribution:
    "Mapové údaje © prispievatelia OpenStreetMap. Názvy miest z GeoNames (CC BY 4.0). Počty článkov z projektu GDELT. Dlhodobé počty z Europol TE-SAT a z Global Terrorism Database (START).",
};

const STRINGS: Record<Lang, Strings> = { en, sk };

const STORAGE_KEY = "lang";

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "en" || saved === "sk") return saved;
  } catch {
    // Storage can be blocked (private mode); fall back to the browser language.
  }
  return navigator.language.toLowerCase().startsWith("sk") ? "sk" : "en";
}

const LangContext = createContext<{ lang: Lang; setLang: (l: Lang) => void } | null>(null);

export function LangProvider({ children, lang: fixed }: { children: ReactNode; lang?: Lang }) {
  const [lang, setLangState] = useState<Lang>(fixed ?? initialLang);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const setLang = (l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      // Not remembering the choice is fine.
    }
  };
  return <LangContext.Provider value={{ lang, setLang }}>{children}</LangContext.Provider>;
}

export function useLang() {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error("useLang must be used inside LangProvider");
  const locale = ctx.lang === "sk" ? "sk-SK" : "en-GB";
  return {
    ...ctx,
    t: STRINGS[ctx.lang],
    locale,
    /** The Slovak text when the page is in Slovak and it exists, otherwise the English text. */
    pick: (textEn: string, textSk?: string | null) => (ctx.lang === "sk" && textSk ? textSk : textEn),
  };
}
