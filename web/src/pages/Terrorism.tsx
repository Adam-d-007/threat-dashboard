import { lazy, Suspense } from "react";
import { ComponentBreakdown } from "../charts/ComponentBreakdown";
import { Banner, Card, LevelBadge, Muted, Segmented, StatusPill } from "../components/ui";
import { useLang } from "../i18n";
import { fmtDate } from "../lib/format";
import type { AnchorReading, Event, RegionAssessment, Run, Timeseries } from "../types/run";
import { BaseRates } from "../terrorism/BaseRates";
import { Incidents } from "../terrorism/Incidents";
import { LatestReports } from "./LatestReports";

type Region = "SK" | "EU";

// Recharts is the largest dependency; load it only when there is a history to draw.
const IndexHistory = lazy(() => import("../charts/IndexHistory").then((m) => ({ default: m.IndexHistory })));

const EU27 = new Set(
  "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE".split(" "),
);

function regionEvents(events: Event[], region: Region): Event[] {
  return region === "EU" ? events : events.filter((e) => EU27.has(e.country) || e.sk_link === "direct");
}

export function TerrorismPage({ run, region, timeseries }: { run: Run; region: Region; timeseries: Timeseries | null }) {
  const { t } = useLang();
  // A provisional score (less than two weeks of history) is recorded but never shown as a level.
  const raw = run.terrorism?.[region] ?? null;
  const assess = raw && !raw.provisional ? raw : null;
  const sis = run.anchors.find((a) => a.id === "anchor_sk_sis") ?? null;
  const events = regionEvents(run.events, region);
  const failing = run.sources.filter((s) => s.status === "failed" || s.status === "stale").length;
  const rows = timeseries?.rows.filter((r) => r.region === region) ?? [];
  // Slovakia: Poland's level and the UK wording for Slovakia. EU: every national level, with
  // the UK wording for all 27 states folded into one summary chip.
  const isFcdo = (id: string) => id.startsWith("anchor_fcdo_");
  const anchors = run.anchors.filter((a) =>
    a.id === "anchor_sk_sis"
      ? false
      : region === "SK"
        ? a.id === "anchor_pl_mswia" || a.id === "anchor_fcdo_sk"
        : !isFcdo(a.id),
  );
  const fcdoAll = region === "EU" ? run.anchors.filter((a) => isFcdo(a.id)) : [];

  return (
    <div className="space-y-6">
      <section className="space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="max-w-3xl">
            <p className="mb-2 text-sm font-medium uppercase tracking-wider text-muted">
              {t.nav.terrorism} · {t.region[region]}
            </p>
            <h1 className="text-3xl font-extrabold leading-[1.1] tracking-tight text-ink sm:text-5xl">{t.heroTitle[region]}</h1>
          </div>
          <Segmented
            label={t.nav.terrorism}
            value={region}
            onChange={(r) => (window.location.hash = r === "SK" ? "terrorism-sk" : "terrorism-eu")}
            options={[
              { value: "SK", label: t.region.SK },
              { value: "EU", label: t.region.EU },
            ]}
          />
        </div>

        <div className="grid gap-4 md:grid-cols-[3fr_2fr]">
          {assess ? <IndicatorCard a={assess} /> : <NotComputedCard availableFrom={raw?.available_from ?? null} />}
          <OfficialCard region={region} sis={sis} />
        </div>

        {anchors.length + fcdoAll.length > 0 && (
          <div>
            <h2 className="mb-2 text-sm font-medium text-muted">{t.anchors}</h2>
            <div className="flex flex-wrap gap-2">
              {anchors.map((a) => (
                <AnchorChip key={a.id} a={a} />
              ))}
              {fcdoAll.length > 0 && <FcdoSummary anchors={fcdoAll} />}
            </div>
          </div>
        )}
      </section>

      <div className="space-y-2">
        {assess?.disagreement && <Banner tone="warn">{t.banners.disagreement}</Banner>}
        {assess?.llm.status === "fallback" && <Banner tone="warn">{t.banners.llmFallback}</Banner>}
        {assess && assess.gates.length > 0 && (
          <Banner tone="info">
            {t.banners.gates}
            <ul className="mt-1 list-disc pl-5">
              {assess.gates.map((g) => (
                <li key={g.id}>
                  {t.gateNames[g.id] ?? g.id} <span className="text-muted">({g.effect})</span>
                </li>
              ))}
            </ul>
          </Banner>
        )}
        {failing > 0 && (
          <Banner tone="warn">
            <a href="#sources">{t.banners.sourcesFailing(failing)}</a>
          </Banner>
        )}
      </div>

      {assess && (
        <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
          <div className="space-y-4">
            <Card title={t.history}>
              {rows.length > 1 ? (
                <Suspense fallback={<div className="h-72" />}>
                  <IndexHistory rows={rows} officialLevel={region === "SK" ? (sis?.level ?? assess.official?.level ?? null) : null} />
                </Suspense>
              ) : (
                <Muted>{t.noEvents}</Muted>
              )}
            </Card>
            <Card title={t.components} id="components">
              <ComponentBreakdown components={assess.components} index={assess.index} events={events} />
            </Card>
          </div>
          <div className="space-y-4">
            <AssessmentCard a={assess} events={events} />
            <ChangesCard run={run} events={events} />
          </div>
        </div>
      )}

      <Incidents
        events={events}
        items={run.items}
        center={region === "SK" ? [48.7, 19.5] : [50.5, 12]}
        zoom={region === "SK" ? 6 : 4}
        asOf={run.run.finished_at}
        tesat={run.tesat}
      />

      <Card title={t.baseRates}>
        <BaseRates tesat={run.tesat} />
      </Card>

      {!assess && <LatestReports items={run.items} />}
    </div>
  );
}

function IndicatorCard({ a }: { a: RegionAssessment }) {
  const { t } = useLang();
  const delta = a.index_prev === null ? null : a.index - a.index_prev;
  return (
    <div className="rounded-2xl border border-line bg-surface p-5 sm:p-6">
      <p className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted">{t.indicator}</p>
      <div className="flex flex-wrap items-center justify-between gap-6">
        <LevelBadge level={a.level} size="xl" />
        <a href="#components" className="text-right text-ink no-underline">
          <div className="text-sm text-muted">{t.index}</div>
          <div className="text-5xl font-bold tabular sm:text-6xl">
            {a.index}
            <span className="text-xl font-normal text-muted">/100</span>
          </div>
          <div className="text-sm text-ink-2">{delta === null || delta === 0 ? t.noChange : t.changeSinceLast(delta)}</div>
        </a>
      </div>
      <p className="mt-4 text-sm text-muted">{t.indicatorNote}</p>
    </div>
  );
}

function NotComputedCard({ availableFrom }: { availableFrom: string | null }) {
  const { t, locale } = useLang();
  return (
    <div className="rounded-2xl border border-dashed border-line bg-surface p-5 sm:p-6">
      <p className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">{t.indicator}</p>
      <p className="text-xl font-semibold">{availableFrom ? t.warmingTitle : t.notComputedTitle}</p>
      <p className="mt-2 text-sm text-ink-2">
        {availableFrom ? t.warmingBody(fmtDate(availableFrom, locale)) : t.notComputedBody}
      </p>
    </div>
  );
}

function OfficialCard({ region, sis }: { region: Region; sis: AnchorReading | null }) {
  const { t, locale } = useLang();
  if (region === "EU") {
    return (
      <div className="rounded-2xl border border-line bg-surface-2 p-5 sm:p-6">
        <p className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">{t.official}</p>
        <p className="text-ink-2">{t.noEuLevel}</p>
      </div>
    );
  }
  return (
    <div className="rounded-2xl border border-line bg-surface-2 p-5 sm:p-6">
      <p className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted">{t.official}</p>
      {sis?.level ? (
        <>
          <LevelBadge level={sis.level} size="md" />
          <p className="mt-3 text-sm text-ink-2">
            {sis.since && t.officialSince(fmtDate(sis.since, locale))} ·{" "}
            <a href={sis.url} target="_blank" rel="noreferrer">
              {t.officialSource}
            </a>
          </p>
          {sis.status !== "ok" && (
            <p className="mt-2 text-sm">
              <StatusPill status={sis.status} />
            </p>
          )}
        </>
      ) : (
        <p className="text-ink-2">{t.officialMissing}</p>
      )}
    </div>
  );
}

function AnchorChip({ a }: { a: AnchorReading }) {
  const { locale } = useLang();
  const n = a.scale.length;
  return (
    <a
      href={a.url}
      target="_blank"
      rel="noreferrer"
      className="group flex items-center gap-3 rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink no-underline hover:bg-surface-2"
      title={a.as_of ? fmtDate(a.as_of, locale) : undefined}
    >
      <span className="font-semibold">{a.country}</span>
      <span className="text-ink-2">{a.name}</span>
      {a.level ? (
        <span className="flex items-center gap-2">
          <span className="flex gap-[2px]" aria-hidden>
            {Array.from({ length: n }, (_, i) => (
              <span key={i} className={`h-3 w-1.5 rounded-sm ${i < a.level! ? "bg-ink-2" : "bg-surface-2"}`} />
            ))}
          </span>
          <span className="font-medium">{a.raw}</span>
          <span className="text-muted tabular">
            {a.level}/{n}
          </span>
        </span>
      ) : (
        <StatusPill status={a.status} />
      )}
    </a>
  );
}

/** UK travel-advice wording for the EU states, counted per phrase, highest first. */
function FcdoSummary({ anchors }: { anchors: AnchorReading[] }) {
  const scale = anchors[0].scale;
  const counts = scale.map((raw) => ({ raw, n: anchors.filter((a) => a.raw === raw).length })).reverse();
  return (
    <a
      href="#sources"
      className="flex items-center gap-3 rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink no-underline hover:bg-surface-2"
    >
      <span className="font-semibold">UK</span>
      <span className="text-ink-2">FCDO</span>
      {counts
        .filter((c) => c.n > 0)
        .map((c) => (
          <span key={c.raw}>
            <span className="font-semibold tabular">{c.n}</span> <span className="text-ink-2">{c.raw}</span>
          </span>
        ))}
    </a>
  );
}

function AssessmentCard({ a, events }: { a: RegionAssessment; events: Event[] }) {
  const { t, pick } = useLang();
  const byId = new Map(events.map((e) => [e.id, e]));
  return (
    <Card title={t.assessment}>
      {a.llm.drivers.length > 0 && (
        <ul className="mb-4 space-y-3">
          {a.llm.drivers.map((d, i) => (
            <li key={i} className="text-sm">
              <p>{pick(d.text_en, d.text_sk)}</p>
              <p className="mt-1 flex flex-wrap gap-x-3 text-xs">
                {d.event_ids.map((id) => (
                  <a key={id} href={`#evt-${id}`}>
                    → {byId.get(id) ? pick(byId.get(id)!.title_en, byId.get(id)!.title_sk) : id}
                  </a>
                ))}
              </p>
            </li>
          ))}
        </ul>
      )}
      {a.llm.what_changed_en && (
        <div className="mb-4">
          <h3 className="mb-1 text-sm font-semibold">{t.whatChanged}</h3>
          <p className="text-sm text-ink-2">{pick(a.llm.what_changed_en, a.llm.what_changed_sk)}</p>
        </div>
      )}
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        {a.llm.confidence && (
          <>
            <dt className="text-muted">{t.confidence}</dt>
            <dd>{t.confidenceNames[a.llm.confidence]}</dd>
          </>
        )}
        {a.llm.model && (
          <>
            <dt className="text-muted">{t.model}</dt>
            <dd>
              {a.llm.model} · {a.llm.status}
            </dd>
          </>
        )}
      </dl>
    </Card>
  );
}

function ChangesCard({ run, events }: { run: Run; events: Event[] }) {
  const { t, pick } = useLang();
  const d = run.diff;
  const byId = new Map(events.map((e) => [e.id, e]));
  const empty =
    !d || (!d.new_event_ids.length && !d.level_changes.length && !d.anchor_changes.length && !d.source_changes.length);
  return (
    <Card title={t.changes}>
      {empty ? (
        <Muted>{t.nothingChanged}</Muted>
      ) : (
        <div className="space-y-3 text-sm">
          {d!.new_event_ids.length > 0 && (
            <div>
              <h3 className="font-semibold">{t.newEvents}</h3>
              <ul className="list-disc pl-5">
                {d!.new_event_ids.map((id) => (
                  <li key={id}>
                    <a href={`#evt-${id}`}>{byId.get(id) ? pick(byId.get(id)!.title_en, byId.get(id)!.title_sk) : id}</a>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {d!.level_changes.map((c) => (
            <p key={c.region}>
              {t.region[c.region]}: {t.levelWord} {c.level_from ?? "–"} → {c.level_to}
            </p>
          ))}
          {d!.anchor_changes.length > 0 && (
            <div>
              <h3 className="font-semibold">{t.anchorChanges}</h3>
              <ul className="list-disc pl-5">
                {d!.anchor_changes.map((c) => (
                  <li key={c.id}>
                    {run.anchors.find((a) => a.id === c.id)?.name ?? c.id}: {c.value_from ?? "–"} → {c.value_to ?? "–"}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {d!.source_changes.length > 0 && (
            <div>
              <h3 className="font-semibold">{t.sourceChanges}</h3>
              <ul className="list-disc pl-5">
                {d!.source_changes.map((c) => (
                  <li key={c.id}>
                    {run.sources.find((s) => s.id === c.id)?.name ?? c.id}: {c.value_from ?? "–"} → {c.value_to ?? "–"}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
