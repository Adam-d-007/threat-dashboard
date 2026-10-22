import { lazy, Suspense, useState } from "react";
import { Sparkline } from "../charts/Sparkline";
import { ArticleLink, Banner, Card, Muted } from "../components/ui";
import { useLang } from "../i18n";
import { fmtDate } from "../lib/format";
import type { Item, Run, Theatre } from "../types/run";
import { LatestReports } from "./LatestReports";

const ReportMap = lazy(() => import("../map/ReportMap"));

// f(1) = 0.375 is a normal day on the shared curve; f(0.5) ≈ 0.21 and f(2) ≈ 0.61.
const NORMAL = 0.375;

export function GeopoliticsPage({ run }: { run: Run }) {
  const { t, pick, locale } = useLang();
  const g = run.geopolitics;
  const itemById = new Map(run.items.map((i) => [i.id, i]));

  return (
    <div className="space-y-6">
      <div className="max-w-3xl">
        <p className="mb-2 text-sm font-medium uppercase tracking-wider text-muted">{t.nav.geopolitics}</p>
        <h1 className="text-3xl font-extrabold leading-[1.1] tracking-tight sm:text-5xl">{t.geoTitle}</h1>
      </div>

      {!g ? (
        <>
          <Banner tone="info">{t.geoNotComputed}</Banner>
          <LatestReports items={run.items} />
        </>
      ) : (
        <>
          {g.brief && (
            <Card title={t.brief}>
              {g.brief.what_changed_en && (
                <p className="mb-3 text-ink-2">{pick(g.brief.what_changed_en, g.brief.what_changed_sk)}</p>
              )}
              <ol className="list-decimal space-y-2 pl-5">
                {g.brief.lines.map((l, i) => (
                  <li key={i}>
                    {pick(l.text_en, l.text_sk)}{" "}
                    {l.item_ids.map((id) => (
                      <SourceLink key={id} item={itemById.get(id)} />
                    ))}
                  </li>
                ))}
              </ol>
            </Card>
          )}

          <section>
            <h2 className="mb-3 text-lg font-semibold">{t.theatres}</h2>
            <div className="grid gap-4 md:grid-cols-2">
              {g.theatres.map((th) => (
                <TheatreCard key={th.id} th={th} itemById={itemById} />
              ))}
            </div>
          </section>

          <TheatreMap theatres={g.theatres} items={run.items} />

          {g.watchlist.length > 0 && (
            <Card title={t.watchlist}>
              <ul className="divide-y divide-line">
                {g.watchlist.map((w, i) => (
                  <li key={i} className="flex gap-4 py-2 text-sm">
                    <span className="w-28 shrink-0 font-semibold tabular">{fmtDate(w.date, locale)}</span>
                    <span>
                      {pick(w.title_en, w.title_sk)}
                      {!w.verified && <span className="ml-2 text-xs text-muted">({t.unverified})</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

/** Reports with a named place, outside terrorism (which has its own map), filtered to one
 * theatre: a report belongs to every theatre whose countries it names. */
function TheatreMap({ theatres, items }: { theatres: Theatre[]; items: Item[] }) {
  const { t, pick } = useLang();
  const [id, setId] = useState("");
  const placed = items.filter(
    (i) => i.classification?.relevant && i.classification.domain !== "terrorism" && i.classification.places.length > 0,
  );
  // Runs written before theatres carried their countries have none; the picker then hides.
  const pickable = theatres.filter((th) => (th.countries ?? []).length > 0);
  const theatre = pickable.find((th) => th.id === id);
  const shown = theatre
    ? placed.filter((i) => i.classification!.countries.some((c) => theatre.countries.includes(c)))
    : placed;
  return (
    <Card title={t.geoMap.title}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        {pickable.length > 0 && (
          <select
            aria-label={t.geoMap.pick}
            value={id}
            onChange={(e) => setId(e.target.value)}
            className="rounded-lg border border-line bg-surface-2 px-2 py-1.5 text-sm text-ink"
          >
            <option value="">{t.geoMap.all}</option>
            {pickable.map((th) => (
              <option key={th.id} value={th.id}>
                {pick(th.name_en, th.name_sk)}
              </option>
            ))}
          </select>
        )}
        <span className="text-sm text-ink-2">{t.geoMap.count(shown.length)}</span>
      </div>
      <Suspense fallback={<div className="h-80 rounded-lg bg-surface-2 sm:h-96" />}>
        <ReportMap items={shown} />
      </Suspense>
      <p className="mt-2 text-xs text-muted">{t.geoMap.note}</p>
    </Card>
  );
}

function SourceLink({ item }: { item: Item | undefined }) {
  if (!item) return null;
  return (
    <ArticleLink href={item.url} className="text-xs text-link">
      [{item.domain}]
    </ArticleLink>
  );
}

function TheatreCard({ th, itemById }: { th: Theatre; itemById: Map<string, Item> }) {
  const { t, pick } = useLang();
  const [open, setOpen] = useState(false);
  const v = th.activity.value;
  const label = v === null ? "–" : v < 0.3 ? t.activityLow : v <= 0.5 ? t.activityNormal : t.activityHigh;
  const ratio =
    th.activity.articles_24h !== null && th.activity.baseline_median
      ? th.activity.articles_24h / th.activity.baseline_median
      : null;

  return (
    <article className="rounded-xl border border-line bg-surface p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-semibold">{pick(th.name_en, th.name_sk)}</h3>
        <Sparkline values={th.sparkline} label={t.activity} />
      </div>

      <div className="mt-3">
        <div className="mb-1 flex justify-between text-xs text-muted">
          <span>{t.activity}</span>
          <span className="font-medium text-ink">
            {label}
            {ratio !== null && <span className="ml-1 text-muted tabular">({ratio.toFixed(1)}×)</span>}
          </span>
        </div>
        <div className="relative h-2.5 rounded-full bg-surface-2">
          {v !== null && <div className="h-full rounded-full" style={{ width: `${v * 100}%`, background: "var(--series-1)" }} />}
          <div className="absolute inset-y-[-3px] w-0.5 bg-ink-2" style={{ left: `${NORMAL * 100}%` }} title={t.activityNormal} />
        </div>
      </div>

      <dl className="mt-3 space-y-1 text-sm text-ink-2">
        {th.acled && <dd>{t.acledEvents(th.acled.events_7d, Math.round(th.acled.avg_week_prev_4))}</dd>}
        {th.tone && (
          <dd>
            {t.tone}: <span className="tabular">{th.tone.value.toFixed(1)}</span>{" "}
            <span className="text-muted tabular">({th.tone.baseline_median.toFixed(1)})</span>
          </dd>
        )}
        {th.sk_angle_en && (
          <dd>
            <span className="font-medium text-ink">{t.slovakAngle}:</span> {pick(th.sk_angle_en, th.sk_angle_sk)}
          </dd>
        )}
      </dl>

      {th.top_items.length > 0 && (
        <div className="mt-3">
          <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="text-sm text-link">
            {open ? "▾" : "▸"} {t.topDevelopments} ({th.top_items.length})
          </button>
          {open && (
            <ul className="mt-2 space-y-2 text-sm">
              {th.top_items.map((ti) => (
                <li key={ti.item_id}>
                  {pick(ti.summary_en, ti.summary_sk)} <SourceLink item={itemById.get(ti.item_id)} />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {th.top_items.length === 0 && <Muted>–</Muted>}
    </article>
  );
}
