import type { Event, Item, Run, Timeseries } from "../types/run";
import type {
  Article,
  GeopoliticsFile,
  Incident,
  IncidentsFile,
  Report,
  ReportsFile,
  Status,
  Summary,
} from "../types/v2";

/** An incident as the pages take it (the old event shape), with its timeline. */
export type IncidentEvent = Event & { reports?: Report[] };
/** A run assembled from the v2 files; status is what each stage of the pipeline did. */
export type RunV2 = Omit<Run, "events"> & { events: IncidentEvent[]; status?: Status };

export type V2Files = {
  status: Status;
  summary: Summary;
  incidents: IncidentsFile;
  reports: ReportsFile;
  geopolitics: GeopoliticsFile;
};
export const V2_NAMES = {
  status: "status.json",
  summary: "summary.json",
  incidents: "incidents/current.json",
  reports: "reports.json",
  geopolitics: "geopolitics.json",
} as const;

/** Only web addresses become links: a feed could carry any scheme. */
const web = (url: string) => /^https?:\/\//i.test(url);

function toEvent(i: Incident): IncidentEvent {
  return {
    id: i.id,
    title_en: i.title_en,
    title_sk: i.title_sk,
    event_type: i.type,
    ideology: i.ideology,
    severity: i.severity,
    date: i.date,
    country: i.country,
    place: i.place,
    sk_link: i.sk_link,
    topic: i.topic,
    item_ids: i.reports.map((r) => r.article_id),
    urls: i.reports.map((r) => r.url).filter(web),
    event_keys: [],
    domains: i.domains,
    has_tier_a: i.has_tier_a,
    best_tier: i.best_tier,
    corroborated: i.corroborated,
    first_seen: i.first_seen,
    last_updated: i.last_updated,
    reports: i.reports.filter((r) => web(r.url)),
  };
}

function toItem(a: Article): Item {
  const l = a.label!;
  return {
    id: a.id,
    source_id: a.source_id,
    tier: a.tier,
    url: a.url,
    title: a.title,
    lang: a.lang,
    published_at: a.published_at,
    published_estimated: false,
    fetched_at: a.fetched_at,
    snippet: a.snippet,
    domain: a.domain,
    also_reported_by: a.also_reported_by,
    gdelt: null,
    classification: {
      status: "llm",
      relevant: true,
      domain: l.domain,
      event_type: l.incident_type ?? "other",
      ideology: l.ideology,
      severity: l.severity,
      sk_link: l.sk_link,
      countries: l.countries,
      places: a.place ? [a.place] : [],
      event_key: null,
      summary_en: l.summary_en,
      summary_sk: l.summary_sk,
      confidence: l.confidence,
    },
    event_id: a.incident_id?.startsWith("inc_") ? a.incident_id : null,
  };
}

/** The five v2 files as the run the pages already know how to show. */
export function assemble(f: V2Files): RunV2 {
  const { status, summary, geopolitics } = f;
  const lines = geopolitics.theatres.flatMap((t) => t.lines);
  const written = geopolitics.theatres.flatMap((t) => (t.lines.length && t.written_at ? [t.written_at] : []));
  const overall = { ok: "ok", degraded: "partial", failed: "failed" } as const;
  return {
    schema_version: 1,
    run: {
      id: summary.run_id ?? status.updated_at.slice(0, 13),
      status: overall[status.overall],
      started_at: status.started_at,
      finished_at: status.updated_at,
      window_start: status.started_at,
      git_sha: status.git_sha,
      counts: {
        fetched: 0,
        from_buffer: 0,
        after_dedupe: 0,
        in_window: 0,
        after_prefilter: status.queue.labelled_24h,
        relevant: f.reports.reports.length,
      },
      llm: null,
    },
    sources: status.sources,
    items: f.reports.reports.filter((a) => a.label && web(a.url)).map(toItem),
    anchors: summary.anchors,
    terrorism: summary.terrorism,
    geopolitics: {
      theatres: geopolitics.theatres,
      // The oldest text shown decides the brief's date: the page then says when it was written.
      brief: lines.length ? { status: "ok", written_at: written.sort()[0] ?? null, lines, what_changed_en: null, what_changed_sk: null } : null,
      watchlist: geopolitics.watchlist,
    },
    events: f.incidents.incidents.map(toEvent),
    diff: summary.diff,
    tesat: summary.tesat,
    sis_annual: summary.sis_annual,
    gtd: summary.gtd,
    sample: false,
    status,
  };
}

/** Sent as ?v= so the browser's own cache misses every hour (the pipeline runs hourly). */
export const hourKey = (now: Date) => now.toISOString().slice(0, 13);

export type V2Result =
  | { kind: "ok"; run: RunV2 }
  | { kind: "unsupported"; version: unknown }
  | { kind: "error"; message: string };

export async function loadV2(base: string, now: Date): Promise<V2Result> {
  const names = Object.entries(V2_NAMES) as [keyof V2Files, string][];
  let bodies: { schema_version?: unknown }[];
  try {
    bodies = await Promise.all(
      names.map(async ([, name]) => {
        const res = await fetch(`${base}/v2/${name}?v=${hourKey(now)}`);
        if (!res.ok) throw new Error(`${name}: HTTP ${res.status}`);
        return res.json();
      }),
    );
  } catch (e) {
    return { kind: "error", message: e instanceof Error ? e.message : String(e) };
  }
  const odd = bodies.find((b) => b?.schema_version !== 2);
  if (odd) return { kind: "unsupported", version: odd?.schema_version };
  const files = Object.fromEntries(names.map(([key], i) => [key, bodies[i]])) as unknown as V2Files;
  return { kind: "ok", run: assemble(files) };
}

export async function loadHistoryV2(base: string, now: Date): Promise<Timeseries | null> {
  const res = await fetch(`${base}/v2/history.json?v=${hourKey(now)}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`history.json: HTTP ${res.status}`);
  return (await res.json()) as Timeseries;
}
