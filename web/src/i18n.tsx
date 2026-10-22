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
  noChange: "no change since last run",
  anchors: "Official levels elsewhere",
  notComputedTitle: "The indicator is not computed yet",
  notComputedBody:
    "Scoring is still being built. Until it runs, this page shows the official level and the latest reports only, never an estimate.",
  sampleBanner:
    "SAMPLE DATA. Everything on this page is made up for design work and means nothing.",
  banners: {
    disagreement:
      "The rules and the language model disagree by more than one level. The level shown is the rules level.",
    gates: "Rules that limited the level in this run:",
    llmFallback: "The language model was unavailable. This run uses rules only.",
    sourcesFailing: (n: number) => `${n} source${n === 1 ? "" : "s"} failed in this run.`,
  },
  gateNames: {
    floor_eu_attack_30d: "Floor 2: corroborated attack in an EU or NATO state in the last 30 days",
    cap_sk_2: "Cap at 2: no qualifying event with a direct Slovak link",
    cap_sk_3: "Cap at 3: no imminent direct threat confirmed by an official source",
    cap_eu_3: "Cap at 3: no mass-casualty attack or wave of attacks in 7 days",
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
    anchors: "Official threat levels and UK travel-advice wording, normalised to 0 to 1.",
    llm: "A language model's reading of the events against the NBAC level definitions.",
  } as Record<string, string>,
  weight: "weight",
  value: "value",
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
  ideologyMix: "Ideology mix, last 90 days",
  baseRates: "Base rates",
  baseRatesPending:
    "Europol TE-SAT yearly figures and GTD history (which ends in 2021) will appear here once they are entered.",
  latestReports: "Latest reports",
  dateEstimated: "date estimated",
  brief: "Daily brief",
  theatres: "Theatres",
  activity: "Activity versus normal",
  activityLow: "below normal",
  activityNormal: "normal",
  activityHigh: "above normal",
  acledEvents: (n: number, avg: number) => `${n} ACLED events in 7 days (4-week average ${avg})`,
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
  hoursAgo: (h: number) => (h < 1 ? "just now" : `${h} h ago`),
  ageAmber: "The data is more than 10 hours old.",
  ageRed: "The data is more than 14 hours old: a scheduled run was probably missed.",
  loading: "Loading data…",
  loadError: "Could not load the data.",
  unsupported: (v: string) =>
    `The data file has version ${v}, which this page does not support. Please reload the page. If the problem continues, the site needs an update.`,
  theme: { dark: "Dark", light: "Light" },
  footer: "Dashboard indicator computed from open sources. Not an official threat assessment.",
  attribution: "Map data © OpenStreetMap contributors.",
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
  noChange: "bez zmeny od poslednej aktualizácie",
  anchors: "Oficiálne úrovne v iných krajinách",
  notComputedTitle: "Ukazovateľ sa zatiaľ nepočíta",
  notComputedBody:
    "Hodnotenie je ešte vo vývoji. Kým nebude spustené, táto stránka zobrazuje len oficiálnu úroveň a najnovšie správy, nikdy odhad.",
  sampleBanner:
    "UKÁŽKOVÉ ÚDAJE. Všetko na tejto stránke je vymyslené pre potreby návrhu a nemá žiadny význam.",
  banners: {
    disagreement:
      "Pravidlá a jazykový model sa líšia o viac ako jednu úroveň. Zobrazená je úroveň podľa pravidiel.",
    gates: "Pravidlá, ktoré v tejto aktualizácii obmedzili úroveň:",
    llmFallback: "Jazykový model nebol dostupný. Táto aktualizácia používa len pravidlá.",
    sourcesFailing: (n: number) =>
      n === 1
        ? "V tejto aktualizácii zlyhal 1 zdroj."
        : `Počet zdrojov, ktoré v tejto aktualizácii zlyhali: ${n}.`,
  },
  gateNames: {
    floor_eu_attack_30d: "Spodná hranica 2: potvrdený útok v štáte EÚ alebo NATO za posledných 30 dní",
    cap_sk_2: "Strop 2: žiadna kvalifikovaná udalosť s priamym prepojením na Slovensko",
    cap_sk_3: "Strop 3: žiadna bezprostredná priama hrozba potvrdená oficiálnym zdrojom",
    cap_eu_3: "Strop 3: žiadny útok s hromadnými obeťami ani séria útokov za 7 dní",
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
      "Oficiálne úrovne ohrozenia a formulácie britských cestovných odporúčaní, prepočítané na stupnicu 0 až 1.",
    llm: "Hodnotenie udalostí jazykovým modelom podľa definícií úrovní NBAC.",
  },
  weight: "váha",
  value: "hodnota",
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
  ideologyMix: "Ideologické zloženie za posledných 90 dní",
  baseRates: "Dlhodobé počty",
  baseRatesPending:
    "Ročné údaje Europolu (TE-SAT) a historické údaje GTD (končia rokom 2021) sa tu zobrazia po ich doplnení.",
  latestReports: "Najnovšie správy",
  dateEstimated: "dátum je odhadnutý",
  brief: "Denný prehľad",
  theatres: "Oblasti",
  activity: "Aktivita oproti bežnému stavu",
  activityLow: "pod bežnou úrovňou",
  activityNormal: "bežná úroveň",
  activityHigh: "nad bežnou úrovňou",
  acledEvents: (n: number, avg: number) => `${n} udalostí ACLED za 7 dní (4-týždňový priemer ${avg})`,
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
  hoursAgo: (h: number) => (h < 1 ? "práve teraz" : `pred ${h} h`),
  ageAmber: "Údaje sú staršie ako 10 hodín.",
  ageRed: "Údaje sú staršie ako 14 hodín: plánovaná aktualizácia pravdepodobne neprebehla.",
  loading: "Načítavajú sa údaje…",
  loadError: "Údaje sa nepodarilo načítať.",
  unsupported: (v: string) =>
    `Súbor s údajmi má verziu ${v}, ktorú táto stránka nepodporuje. Obnovte, prosím, stránku. Ak problém pretrváva, stránku je potrebné aktualizovať.`,
  theme: { dark: "Tmavý", light: "Svetlý" },
  footer: "Ukazovateľ dashboardu vypočítaný z otvorených zdrojov. Nejde o oficiálne hodnotenie hrozby.",
  attribution: "Mapové údaje © prispievatelia OpenStreetMap.",
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
