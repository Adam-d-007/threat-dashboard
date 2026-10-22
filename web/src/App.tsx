import { useEffect, useState } from "react";
import { useLang, type Lang } from "./i18n";
import { dataAge } from "./lib/age";
import { loadLatest, type LoadResult } from "./lib/data";
import type { Run, SourceHealth } from "./types/run";

const systemNow = () => new Date();

export default function App({ now = systemNow }: { now?: () => Date }) {
  const { t } = useLang();
  const [result, setResult] = useState<LoadResult | null>(null);

  useEffect(() => {
    loadLatest(now()).then(setResult);
  }, [now]);

  return (
    <div className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 py-4">
      <Header run={result?.kind === "ok" ? result.run : null} now={now()} />
      <main className="flex-1">
        {result === null && <p className="text-zinc-400">{t.loading}</p>}
        {result?.kind === "error" && (
          <ErrorPanel text={`${t.loadError} (${result.message})`} />
        )}
        {result?.kind === "unsupported" && (
          <ErrorPanel text={t.unsupported(String(result.version))} />
        )}
        {result?.kind === "ok" && <RunView run={result.run} />}
      </main>
      <footer className="mt-8 border-t border-zinc-800 pt-3 text-xs text-zinc-400">
        {t.footer}
      </footer>
    </div>
  );
}

function Header({ run, now }: { run: Run | null; now: Date }) {
  const { t, lang, setLang, locale } = useLang();
  const age = run ? dataAge(run.run.finished_at, now) : null;
  const ageClass =
    age?.level === "red"
      ? "bg-red-600 text-white"
      : age?.level === "amber"
        ? "bg-amber-500 text-black"
        : "bg-zinc-800 text-zinc-200";

  return (
    <header className="mb-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">{t.title}</h1>
        <LangSwitch lang={lang} setLang={setLang} />
      </div>
      {run && age && (
        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-zinc-400">{t.lastRun}:</span>
          <time dateTime={run.run.finished_at}>
            {new Date(run.run.finished_at).toLocaleString(locale, {
              day: "numeric",
              month: "short",
              year: "numeric",
              hour: "2-digit",
              minute: "2-digit",
              timeZoneName: "short",
            })}
          </time>
          <span data-testid="age" data-level={age.level} className={`rounded px-2 py-0.5 ${ageClass}`}>
            {t.hoursAgo(Math.floor(age.hours))}
          </span>
        </div>
      )}
      {age?.level === "red" && <Banner tone="red">{t.ageRed}</Banner>}
      {age?.level === "amber" && <Banner tone="amber">{t.ageAmber}</Banner>}
      {run?.run.status === "partial" && <Banner tone="amber">{t.runPartial}</Banner>}
    </header>
  );
}

function LangSwitch({ lang, setLang }: { lang: Lang; setLang: (l: Lang) => void }) {
  return (
    <div className="flex overflow-hidden rounded border border-zinc-700 text-sm" role="group">
      {(["en", "sk"] as const).map((l) => (
        <button
          key={l}
          type="button"
          aria-pressed={lang === l}
          onClick={() => setLang(l)}
          className={`px-2 py-1 ${lang === l ? "bg-zinc-200 text-black" : "text-zinc-300"}`}
        >
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

function Banner({ tone, children }: { tone: "red" | "amber"; children: React.ReactNode }) {
  const cls =
    tone === "red"
      ? "border-red-500 bg-red-950 text-red-100"
      : "border-amber-500 bg-amber-950 text-amber-100";
  return (
    <p role="alert" className={`mt-2 rounded border px-3 py-2 text-sm ${cls}`}>
      {children}
    </p>
  );
}

function ErrorPanel({ text }: { text: string }) {
  return (
    <p role="alert" className="rounded border border-red-500 bg-red-950 px-3 py-2 text-red-100">
      {text}
    </p>
  );
}

function RunView({ run }: { run: Run }) {
  const { t, locale } = useLang();
  return (
    <>
      <section>
        <h2 className="mb-2 text-lg font-semibold">
          {t.items} ({run.items.length})
        </h2>
        {run.items.length === 0 && <p className="text-zinc-400">{t.noItems}</p>}
        <ul className="divide-y divide-zinc-800">
          {run.items.map((item) => (
            <li key={item.id} className="py-2">
              <a href={item.url} target="_blank" rel="noreferrer" className="hover:underline">
                {item.title}
              </a>
              <div className="text-xs text-zinc-400">
                {item.domain} · {item.tier} ·{" "}
                {new Date(item.published_at).toLocaleString(locale, {
                  dateStyle: "short",
                  timeStyle: "short",
                })}
                {item.published_estimated && ` (${t.dateEstimated})`} · {item.lang}
              </div>
            </li>
          ))}
        </ul>
      </section>
      <section className="mt-6">
        <h2 className="mb-2 text-lg font-semibold">{t.sources}</h2>
        <ul className="text-sm">
          {run.sources.map((s) => (
            <SourceRow key={s.id} source={s} />
          ))}
        </ul>
      </section>
    </>
  );
}

function SourceRow({ source: s }: { source: SourceHealth }) {
  const { t, locale } = useLang();
  const color =
    s.status === "ok" ? "text-green-400" : s.status === "disabled" ? "text-zinc-500" : "text-red-400";
  return (
    <li className="py-1">
      <span className="font-medium">{s.name}</span>{" "}
      <span className={color}>{t.sourceStatus[s.status]}</span>{" "}
      <span className="text-zinc-400">
        · {s.items} · {t.lastSuccess}:{" "}
        {s.last_success
          ? new Date(s.last_success).toLocaleString(locale, { dateStyle: "short", timeStyle: "short" })
          : t.never}
        {s.error && ` · ${s.error}`}
      </span>
    </li>
  );
}
