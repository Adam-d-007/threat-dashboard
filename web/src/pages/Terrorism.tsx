import { lazy, Suspense } from "react";
import { ComponentBreakdown } from "../charts/ComponentBreakdown";
import { Banner, Card, LevelBadge, Muted, Segmented, StatusPill } from "../components/ui";
import { useLang } from "../i18n";
import { fmtDate } from "../lib/format";
import type { AnchorReading, Event, RegionAssessment, Run, Timeseries } from "../types/run";
import { BaseRates } from "../terrorism/BaseRates";
import { SisAnnualPoints } from "../terrorism/SisAnnual";
import { Incidents } from "../terrorism/Incidents";
import { LatestReports } from "./LatestReports";

type Region = "SK" | "EU";

// Recharts is the largest dependency; load it only when there is a history to draw.
const IndexHistory = lazy(() => import("../charts/IndexHistory").then((m) => ({ default: m.IndexHistory })));

const EU27 = new Set(
  "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE".split(" "),
);

// NATO members outside the EU; with the EU-27 they are where every kind of incident counts.
const NATO_NON_EU = new Set(["AL", "CA", "IS", "ME", "MK", "NO", "TR", "GB", "US"]);

/** The incidents the score counts (pipeline/score/components.py): outside the EU and NATO only
 * terrorism, so acts of war in Ukraine or Russia are not listed as attacks. */
function regionEvents(events: Event[], region: Region): Event[] {
  const counted = events.filter(
    (e) => EU27.has(e.country) || NATO_NON_EU.has(e.country) || e.topic === "terrorism",
  );
  return region === "EU" ? counted : counted.filter((e) => EU27.has(e.country) || e.sk_link === "direct");
}

export function TerrorismPage({ run, region, timeseries }: { run: Run; region: Region; timeseries: Timeseries | null }) {
  const { t } = useLang();
  // A provisional score (less than two weeks of history) is shown with a label saying so.
  const assess = run.terrorism?.[region] ?? null;
  const sis = run.anchors.find((a) => a.id === "anchor_sk_sis") ?? null;
  const events = regionEvents(run.events, region);
  // As the pipeline's run status: a source that failed but succeeded within 24 hours is not
  // flagged (the Council's feed was slow once on 2026-10-27); the sources page lists it.
  const runAt = new Date(run.run.started_at).getTime();
  const failing = run.sources.filter(
    (s) =>
      s.status === "stale" ||
      (s.status === "failed" && (!s.last_success || runAt - new Date(s.last_success).getTime() > 24 * 3_600_000)),
  ).length;
  const newHere = (run.diff?.new_event_ids ?? []).filter((id) => events.some((e) => e.id === id)).length;
  const rows = timeseries?.rows.filter((r) => r.region === region) ?? [];
  // National levels: Poland's for Slovakia, every published one for the EU. Travel advice: each
  // government's reading for Slovakia, or for the EU one summary chip per government.
  const national = run.anchors.filter(
    (a) => a.kind !== "travel" && a.id !== "anchor_sk_sis" && (region === "EU" || a.id === "anchor_pl_mswia"),
  );
  const travel = run.anchors.filter((a) => a.kind === "travel");
  const travelSk = region === "SK" ? travel.filter((a) => a.country === "SK") : [];
  const groups = new Map<string, AnchorReading[]>();
  for (const a of travel) groups.set(a.issuer ?? "", [...(groups.get(a.issuer ?? "") ?? []), a]);
  const travelByIssuer = region === "EU" ? [...groups.values()].filter((g) => g.length > 1) : [];

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
          {assess ? <IndicatorCard a={assess} newEvents={newHere} /> : <NotComputedCard />}
          <OfficialCard region={region} sis={sis} />
        </div>

        {national.length > 0 && (
          <div>
            <h2 className="text-sm font-medium text-muted">{t.anchors}</h2>
            <p className="mb-2 max-w-3xl text-xs text-muted">{t.anchorsExplain}</p>
            <div className="flex flex-wrap gap-2">
              {national.map((a) => (
                <AnchorChip key={a.id} a={a} />
              ))}
            </div>
          </div>
        )}
        {travelSk.length + travelByIssuer.length > 0 && (
          <div>
            <h2 className="text-sm font-medium text-muted">{t.travelAdvice(travelSk.length || travelByIssuer.length)}</h2>
            <p className="mb-2 max-w-3xl text-xs text-muted">{region === "SK" ? t.travelExplainSK : t.travelExplainEU}</p>
            <div className="flex flex-wrap items-start gap-2">
              {travelSk.map((a) => (
                <AnchorChip key={a.id} a={a} />
              ))}
              {travelByIssuer.map((g) => (
                <TravelSummary key={g[0].issuer} anchors={g} />
              ))}
            </div>
          </div>
        )}
      </section>

      <div className="space-y-2">
        {assess?.disagreement && <Banner tone="info">{t.banners.disagreement}</Banner>}
        {assess?.llm.status === "fallback" && <Banner tone="warn">{t.banners.llmFallback}</Banner>}
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
        <BaseRates tesat={run.tesat} gtd={run.gtd ?? null} region={region} />
      </Card>

      {region === "SK" && run.sis_annual && (
        <Card title={t.sisAnnual.title}>
          <SisAnnualPoints sis={run.sis_annual} />
        </Card>
      )}

      {!assess && <LatestReports items={run.items} />}
    </div>
  );
}

function IndicatorCard({ a, newEvents }: { a: RegionAssessment; newEvents: number }) {
  const { t, locale } = useLang();
  const delta = a.index_prev === null ? null : a.index - a.index_prev;
  return (
    <div className={`rounded-2xl border bg-surface p-5 sm:p-6 ${a.provisional ? "border-dashed border-ink-2" : "border-line"}`}>
      <p className="mb-4 flex flex-wrap items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted">
        {t.indicator}
        {a.provisional && (
          <span className="rounded-md bg-surface-2 px-2 py-0.5 text-xs normal-case tracking-normal text-ink">{t.provisional}</span>
        )}
      </p>
      <div className="flex flex-wrap items-center justify-between gap-6">
        <LevelBadge level={a.level} size="xl" />
        <a href="#components" className="text-right text-ink no-underline">
          <div className="text-sm text-muted">{t.index}</div>
          <div className="text-5xl font-bold tabular sm:text-6xl">
            {a.index}
            <span className="text-xl font-normal text-muted">/100</span>
          </div>
          <div className="text-sm text-ink-2">
            {delta === null || delta === 0 ? t.noChange : t.changeSinceLast(delta)}
            {newEvents > 0 && ` · ${t.newSinceLast(newEvents)}`}
          </div>
        </a>
      </div>
      <p className="mt-4 text-sm text-muted">
        {a.provisional && a.available_from ? t.provisionalNote(fmtDate(a.available_from, locale)) : t.indicatorNote}
      </p>
    </div>
  );
}

function NotComputedCard() {
  const { t } = useLang();
  return (
    <div className="rounded-2xl border border-dashed border-line bg-surface p-5 sm:p-6">
      <p className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">{t.indicator}</p>
      <p className="text-xl font-semibold">{t.notComputedTitle}</p>
      <p className="mt-2 text-sm text-ink-2">{t.notComputedBody}</p>
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
  const { t } = useLang();
  const n = a.scale.length;
  return (
    <a
      href={a.url}
      target="_blank"
      rel="noreferrer"
      className="group flex items-center gap-3 rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink no-underline hover:border-ink-2 hover:bg-surface-2"
      title={a.level ? t.chipTitle(a.name, a.raw ?? "", a.level, n) : a.name}
    >
      <span className="font-semibold">{a.kind === "travel" ? a.issuer : a.country}</span>
      <span className="text-ink-2 group-hover:underline">{a.name}</span>
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
      <span aria-hidden className="text-muted group-hover:text-ink">
        ↗
      </span>
    </a>
  );
}

/** One government's travel advice for the EU states, counted per level, highest first; opens
 * to every country with a link to that government's page for it. */
function TravelSummary({ anchors }: { anchors: AnchorReading[] }) {
  const scale = anchors[0].scale;
  const counts = scale.map((raw) => ({ raw, n: anchors.filter((a) => a.raw === raw).length })).reverse();
  const sorted = [...anchors].sort((x, y) => (y.level ?? 0) - (x.level ?? 0) || x.country.localeCompare(y.country));
  return (
    <details className="group rounded-lg border border-line bg-surface text-sm text-ink open:basis-full hover:border-ink-2">
      <summary className="flex cursor-pointer list-none items-center gap-3 px-3 py-2 hover:bg-surface-2">
        <span className="font-semibold">{anchors[0].issuer}</span>
        <span className="text-ink-2">{anchors[0].name.replace(" travel advice", "")}</span>
        {counts
          .filter((c) => c.n > 0)
          .map((c) => (
            <span key={c.raw}>
              <span className="font-semibold tabular">{c.n}</span> <span className="text-ink-2">{c.raw}</span>
            </span>
          ))}
        <span aria-hidden className="text-muted transition-transform group-open:rotate-90">
          ▸
        </span>
      </summary>
      <ul className="grid gap-x-6 gap-y-1 border-t border-line px-3 py-2 sm:grid-cols-2 lg:grid-cols-3">
        {sorted.map((a) => (
          <li key={a.id} className="flex justify-between gap-3">
            <a href={a.url} target="_blank" rel="noreferrer" className="text-link">
              {a.country} ↗
            </a>
            <span className="text-ink-2">
              {a.raw ?? "–"} <span className="text-muted tabular">{a.level ? `${a.level}/${a.scale.length}` : ""}</span>
            </span>
          </li>
        ))}
      </ul>
    </details>
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
                {d!.anchor_changes.map((c) => {
                  const a = run.anchors.find((x) => x.id === c.id);
                  const label = a ? (a.kind === "travel" ? `${a.name} (${a.country})` : a.name) : c.id;
                  return (
                    <li key={c.id}>
                      {label}: {c.value_from ?? "–"} → {c.value_to ?? "–"}
                    </li>
                  );
                })}
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
