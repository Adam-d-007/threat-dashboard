export function fmtDate(iso: string, locale: string): string {
  return new Date(iso).toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" });
}

export function fmtDateTime(iso: string, locale: string): string {
  return new Date(iso).toLocaleString(locale, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Level (1-4) from a 0-1 pressure, with the thresholds 0.25, 0.50 and 0.75 from the spec. */
export function levelOf(p: number): 1 | 2 | 3 | 4 {
  return p >= 0.75 ? 4 : p >= 0.5 ? 3 : p >= 0.25 ? 2 : 1;
}

export const ROUTES = ["geopolitics", "terrorism-sk", "terrorism-eu", "sources", "method"] as const;
export type Route = (typeof ROUTES)[number];
export const DEFAULT_ROUTE: Route = "terrorism-sk";

export function parseRoute(hash: string): Route {
  const r = hash.replace(/^#/, "");
  return (ROUTES as readonly string[]).includes(r) ? (r as Route) : DEFAULT_ROUTE;
}
