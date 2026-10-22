import type { ReactNode } from "react";
import { useLang } from "../i18n";
import { dataAge } from "../lib/age";
import type { Route } from "../lib/format";
import { fmtDateTime } from "../lib/format";
import type { Theme } from "../lib/theme";
import type { Run } from "../types/run";
import { Banner, Segmented } from "./ui";

export function Layout({
  route,
  run,
  now,
  theme,
  setTheme,
  runIds,
  picked,
  onPick,
  children,
}: {
  route: Route;
  run: Run | null;
  now: Date;
  theme: Theme;
  setTheme: (t: Theme) => void;
  runIds: string[];
  picked: string | null;
  onPick: (id: string) => void;
  children: ReactNode;
}) {
  const { t, lang, setLang, locale } = useLang();
  const age = run ? dataAge(run.run.finished_at, now) : null;
  const tabs: { href: string; label: string; active: boolean }[] = [
    { href: "#terrorism-sk", label: t.nav.terrorism, active: route.startsWith("terrorism") },
    { href: "#geopolitics", label: t.nav.geopolitics, active: route === "geopolitics" },
    { href: "#sources", label: t.nav.sources, active: route === "sources" },
    { href: "#method", label: t.nav.method, active: route === "method" },
  ];
  const ageClass =
    age?.level === "red"
      ? "bg-level-4 text-white"
      : age?.level === "amber"
        ? "bg-level-2 text-black"
        : "bg-surface-2 text-ink-2";

  return (
    <div className="min-h-screen">
      {run?.sample && (
        <div className="sticky top-0 z-[1100] bg-sample px-4 py-1.5 text-center text-sm font-semibold text-white">
          {t.sampleBanner}
        </div>
      )}
      <header className="border-b border-line bg-surface/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <a href="#terrorism-sk" className="text-lg font-bold tracking-tight text-ink no-underline">
            {t.siteName}
          </a>
          <nav className="order-3 -mx-1 flex w-full gap-1 overflow-x-auto sm:order-none sm:w-auto">
            {tabs.map((tab) => (
              <a
                key={tab.href}
                href={tab.href}
                aria-current={tab.active ? "page" : undefined}
                className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm no-underline ${
                  tab.active ? "bg-surface-2 font-semibold text-ink" : "text-ink-2 hover:text-ink"
                }`}
              >
                {tab.label}
              </a>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {runIds.length > 1 && (
              <select
                aria-label={t.runPicker}
                value={picked ?? runIds[0]}
                onChange={(e) => onPick(e.target.value)}
                className="rounded-lg border border-line bg-surface-2 px-2 py-1.5 text-xs text-ink"
              >
                {runIds.map((id, i) => (
                  <option key={id} value={id}>
                    {i === 0 ? `${id} (${t.latest})` : id}
                  </option>
                ))}
              </select>
            )}
            {run && age && (
              <span className="hidden text-xs text-muted md:inline">
                {t.lastRun} {fmtDateTime(run.run.finished_at, locale)}
              </span>
            )}
            {age && (
              <span data-testid="age" data-level={age.level} className={`rounded-md px-2 py-1 text-xs tabular ${ageClass}`}>
                {t.hoursAgo(Math.floor(age.hours))}
              </span>
            )}
            <Segmented
              label="Language"
              value={lang}
              onChange={setLang}
              options={[
                { value: "sk", label: "SK" },
                { value: "en", label: "EN" },
              ]}
            />
            <button
              type="button"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              className="rounded-lg border border-line px-2.5 py-1.5 text-sm text-ink-2 hover:bg-surface-2"
              aria-label={theme === "dark" ? t.theme.light : t.theme.dark}
              title={theme === "dark" ? t.theme.light : t.theme.dark}
            >
              {theme === "dark" ? "☀" : "☾"}
            </button>
          </div>
        </div>
      </header>
      <div className="mx-auto max-w-6xl space-y-2 px-4 pt-3 empty:hidden">
        {picked && run && (
          <Banner tone="info">
            {t.viewingOld(run.run.id)}{" "}
            <button type="button" className="underline" onClick={() => onPick(runIds[0])}>
              {t.backToLatest}
            </button>
          </Banner>
        )}
        {!picked && age?.level === "red" && <Banner tone="crit">{t.ageRed}</Banner>}
        {!picked && age?.level === "amber" && <Banner tone="warn">{t.ageAmber}</Banner>}
      </div>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
      <footer className="border-t border-line">
        <div className="mx-auto max-w-6xl space-y-1 px-4 py-5 text-xs text-muted">
          <p className="font-medium text-ink-2">{t.footer}</p>
          <p>{t.attribution}</p>
        </div>
      </footer>
    </div>
  );
}
