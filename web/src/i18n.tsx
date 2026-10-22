import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Lang = "en" | "sk";

const en = {
  title: "Threat dashboard",
  lastRun: "Last run",
  hoursAgo: (h: number) => `${h} h ago`,
  ageAmber: "The data is more than 10 hours old.",
  ageRed: "The data is more than 14 hours old: a scheduled run was probably missed.",
  runPartial: "Some sources failed in this run. See the source list below.",
  loading: "Loading data…",
  loadError: "Could not load the data.",
  unsupported: (v: string) =>
    `The data file has version ${v}, which this page does not support. Please reload the page. If the problem continues, the site needs an update.`,
  items: "Items in this run",
  noItems: "No items in this run.",
  dateEstimated: "date estimated",
  sources: "Sources",
  sourceStatus: { ok: "ok", stale: "stale", failed: "failed", disabled: "disabled" },
  lastSuccess: "last success",
  never: "never",
  footer: "Dashboard indicator computed from open sources. Not an official threat assessment.",
};

export type Strings = typeof en;

// Typed as Strings so a missing Slovak string is a compile error.
const sk: Strings = {
  title: "Prehľad hrozieb",
  lastRun: "Posledná aktualizácia",
  hoursAgo: (h: number) => `pred ${h} h`,
  ageAmber: "Údaje sú staršie ako 10 hodín.",
  ageRed: "Údaje sú staršie ako 14 hodín: plánovaná aktualizácia pravdepodobne neprebehla.",
  runPartial: "Niektoré zdroje v tejto aktualizácii zlyhali. Pozrite si zoznam zdrojov nižšie.",
  loading: "Načítavajú sa údaje…",
  loadError: "Údaje sa nepodarilo načítať.",
  unsupported: (v: string) =>
    `Súbor s údajmi má verziu ${v}, ktorú táto stránka nepodporuje. Obnovte, prosím, stránku. Ak problém pretrváva, stránku je potrebné aktualizovať.`,
  items: "Položky z tejto aktualizácie",
  noItems: "V tejto aktualizácii nie sú žiadne položky.",
  dateEstimated: "dátum je odhadnutý",
  sources: "Zdroje",
  sourceStatus: { ok: "v poriadku", stale: "neaktuálny", failed: "zlyhal", disabled: "vypnutý" },
  lastSuccess: "posledný úspech",
  never: "nikdy",
  footer:
    "Ukazovateľ dashboardu vypočítaný z otvorených zdrojov. Nejde o oficiálne hodnotenie hrozby.",
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
  return { ...ctx, t: STRINGS[ctx.lang], locale: ctx.lang === "sk" ? "sk-SK" : "en-GB" };
}
