import type { Run } from "../types/run";

export const SUPPORTED_SCHEMA_VERSIONS = [1];

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

/** The most recent run slot at or before `now`, e.g. "2026-10-22T13". Used to bust caches. */
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
  let res: Response;
  try {
    res = await fetch(`${dataBaseUrl()}/latest.json?v=${slotKey(now)}`);
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
