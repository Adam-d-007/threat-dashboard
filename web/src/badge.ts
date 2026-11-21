import type { Status, Summary } from "./types/v2";

/** The embeddable badge (badge.html): the official SIS level first, this site's estimate beside
 * it marked as unofficial, the date of the data, and greyed out when the data is over 24 hours
 * old. It is shown on other people's pages, away from the explanation, so it never shows the
 * estimate alone. Built with DOM calls only: nothing from the data is ever parsed as HTML. */

type Lang = "sk" | "en";
const STALE_AFTER_H = 24;
const TEXT = {
  sk: {
    head: "Teroristické ohrozenie · Slovensko",
    official: "Oficiálny stupeň (SIS)",
    ours: "Neoficiálny odhad stránky Monitor hrozieb",
    levels: ["Nízky", "Zvýšený", "Vysoký", "Kritický"],
    none: "nedostupný",
    notYet: "zatiaľ sa nepočíta",
    provisional: "predbežný",
    index: (i: number) => `index ${i}/100`,
    from: (when: string) => `Údaje z ${when}`,
    stale: "Údaje sú staršie ako 24 hodín.",
    site: "Monitor hrozieb",
    failed: "Údaje sa nepodarilo načítať.",
    locale: "sk-SK",
  },
  en: {
    head: "Terrorist threat · Slovakia",
    official: "Official level (SIS)",
    ours: "Unofficial estimate by Threat monitor",
    levels: ["Low", "Elevated", "High", "Critical"],
    none: "unavailable",
    notYet: "not computed yet",
    provisional: "provisional",
    index: (i: number) => `index ${i}/100`,
    from: (when: string) => `Data from ${when}`,
    stale: "The data is more than 24 hours old.",
    site: "Threat monitor",
    failed: "The data could not be loaded.",
    locale: "en-GB",
  },
};

function el(tag: string, cls: string, text?: string): HTMLElement {
  const e = document.createElement(tag);
  e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function row(what: string, level: number | null, name: string, extra?: string): HTMLElement {
  const r = el("div", "row");
  r.append(el("span", `num${level ? ` l${level}` : ""}`, level ? String(level) : "–"));
  const text = el("div", "");
  text.append(el("div", "what", what), el("div", "name", extra ? `${name} · ${extra}` : name));
  r.append(text);
  return r;
}

export function renderBadge(root: HTMLElement, summary: Summary, status: Status, now: Date, lang: Lang, siteUrl: string): void {
  const t = TEXT[lang];
  const stale = now.getTime() - new Date(status.updated_at).getTime() > STALE_AFTER_H * 3_600_000;
  const box = el("div", `badge${stale ? " stale" : ""}`);
  box.append(el("p", "head", t.head));

  const sis = summary.anchors.find((a) => a.id === "anchor_sk_sis");
  box.append(row(t.official, sis?.level ?? null, sis?.level ? t.levels[sis.level - 1] : t.none));

  const sk = summary.terrorism?.SK;
  const extra = sk ? [t.index(sk.index), ...(sk.provisional ? [t.provisional] : [])].join(" · ") : undefined;
  box.append(row(t.ours, sk?.level ?? null, sk ? t.levels[sk.level - 1] : t.notYet, extra));

  const foot = el("p", "foot");
  const when = new Date(status.updated_at).toLocaleString(t.locale, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  foot.append(`${stale ? `${t.stale} ` : ""}${t.from(when)} · `);
  const link = el("a", "", `${t.site} ↗`) as HTMLAnchorElement;
  link.href = siteUrl;
  link.target = "_blank";
  link.rel = "noopener";
  foot.append(link);
  box.append(foot);
  root.replaceChildren(box);
}

async function main(root: HTMLElement): Promise<void> {
  const lang: Lang = new URLSearchParams(window.location.search).get("lang") === "en" ? "en" : "sk";
  document.documentElement.lang = lang;
  const base = String(import.meta.env.VITE_DATA_BASE_URL ?? "").replace(/\/$/, "");
  const hour = new Date().toISOString().slice(0, 13);
  try {
    const [summary, status] = await Promise.all(
      ["summary.json", "status.json"].map(async (name) => {
        const res = await fetch(`${base}/v2/${name}?v=${hour}`);
        if (!res.ok) throw new Error(`${name}: HTTP ${res.status}`);
        return res.json();
      }),
    );
    renderBadge(root, summary as Summary, status as Status, new Date(), lang, `${window.location.origin}/`);
  } catch (e) {
    console.error(e);
    root.replaceChildren(el("div", "badge stale", TEXT[lang].failed));
  }
}

// In the tests there is no badge page: the module is imported for renderBadge only.
const root = document.getElementById("badge");
if (root) void main(root);
