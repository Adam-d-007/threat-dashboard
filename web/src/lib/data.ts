import type { Run, Timeseries } from "../types/run";

export const SUPPORTED_SCHEMA_VERSIONS = [1];

/** True on builds made with VITE_SAMPLE_DATA=true (the dev branch deploy and local design work).
 * The site then renders the bundled, made-up sample files and says so on every page. */
export const SAMPLE_MODE = import.meta.env.VITE_SAMPLE_DATA === "true";

// Runs start at 04:05 and 13:05 UTC.
const SLOTS_UTC: [number, number][] = [
  [4, 5],
  [13, 5],
];

export function dataBaseUrl(): string {
  const url = import.meta.env.VITE_DATA_BASE_URL;
  if (!url) throw new Error("VITE_DATA_BASE_URL is not set");
  return url.replace(/\/$/, "");
}

/**
 * The most recent run slot at or before `now`, e.g. "2026-10-22T13". Sent as ?v= so the
 * browser's own cache misses after each run. raw.githubusercontent.com's CDN ignores query
 * strings (checked 2026-10-22), so new data can still take up to its 5-minute max-age to appear.
 */
export function slotKey(now: Date): string {
  const candidates: Date[] = [];
  for (const dayOffset of [0, -1]) {
    for (const [h, m] of SLOTS_UTC) {
      const d = new Date(
        Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + dayOffset, h, m),
      );
      if (d <= now) candidates.push(d);
    }
  }
  const latest = candidates.reduce((a, b) => (a > b ? a : b));
  return latest.toISOString().slice(0, 13);
}

export type LoadResult =
  | { kind: "ok"; run: Run }
  | { kind: "unsupported"; version: unknown }
  | { kind: "error"; message: string };

export async function loadLatest(now: Date = new Date()): Promise<LoadResult> {
  let data: { schema_version?: unknown };
  if (SAMPLE_MODE) {
    data = (await import("../sample/latest.json")).default;
  } else {
    let res: Response;
    try {
      res = await fetch(`${dataBaseUrl()}/latest.json?v=${slotKey(now)}`);
    } catch (e) {
      return { kind: "error", message: String(e) };
    }
    if (!res.ok) return { kind: "error", message: `HTTP ${res.status}` };
    data = await res.json();
  }
  if (!SUPPORTED_SCHEMA_VERSIONS.includes(data?.schema_version as number)) {
    return { kind: "unsupported", version: data?.schema_version };
  }
  return { kind: "ok", run: data as unknown as Run };
}

/** Ids of the stored runs, newest first (runs/index.json), or [] when there is no index. */
export async function loadRunIndex(now: Date = new Date()): Promise<string[]> {
  if (SAMPLE_MODE) return [];
  const res = await fetch(`${dataBaseUrl()}/runs/index.json?v=${slotKey(now)}`);
  if (!res.ok) return [];
  const runs = (await res.json())?.runs;
  return Array.isArray(runs) ? runs : [];
}

/** One stored run (runs/<id>.json), checked like latest.json. */
export async function loadRun(id: string): Promise<LoadResult> {
  let res: Response;
  try {
    res = await fetch(`${dataBaseUrl()}/runs/${encodeURIComponent(id)}.json`);
  } catch (e) {
    return { kind: "error", message: String(e) };
  }
  if (!res.ok) return { kind: "error", message: `HTTP ${res.status}` };
  const data = await res.json();
  if (!SUPPORTED_SCHEMA_VERSIONS.includes(data?.schema_version)) {
    return { kind: "unsupported", version: data?.schema_version };
  }
  return { kind: "ok", run: data as Run };
}

/** The index history, or null when none exists yet (before scoring runs). */
export async function loadTimeseries(now: Date = new Date()): Promise<Timeseries | null> {
  if (SAMPLE_MODE) return (await import("../sample/timeseries.json")).default as unknown as Timeseries;
  const res = await fetch(`${dataBaseUrl()}/timeseries.json?v=${slotKey(now)}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`timeseries.json: HTTP ${res.status}`);
  return (await res.json()) as Timeseries;
}
