import { Card, Muted } from "../components/ui";
import { useLang } from "../i18n";
import { fmtDateTime } from "../lib/format";
import type { Item } from "../types/run";

/** The newest items of the run, for pages whose computed panels do not exist yet. */
export function LatestReports({ items, limit = 40 }: { items: Item[]; limit?: number }) {
  const { t, locale } = useLang();
  const newest = [...items].sort((a, b) => b.published_at.localeCompare(a.published_at)).slice(0, limit);
  return (
    <Card title={`${t.latestReports} (${items.length})`}>
      {newest.length === 0 ? (
        <Muted>{t.noEvents}</Muted>
      ) : (
        <ul className="divide-y divide-line">
          {newest.map((item) => (
            <li key={item.id} className="py-2.5">
              <a href={item.url} target="_blank" rel="noreferrer" className="font-medium text-ink hover:underline">
                {item.title}
              </a>
              <div className="mt-0.5 text-xs text-muted">
                {item.domain} · {item.tier} · {fmtDateTime(item.published_at, locale)}
                {item.published_estimated && ` (${t.dateEstimated})`} · {item.lang}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
