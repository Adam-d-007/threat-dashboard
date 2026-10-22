import { Card, Muted, StatusPill } from "../components/ui";
import { useLang } from "../i18n";
import { fmtDate, fmtDateTime } from "../lib/format";
import type { Run } from "../types/run";

export function SourcesPage({ run }: { run: Run }) {
  const { t, locale } = useLang();
  const order = { failed: 0, stale: 1, ok: 2, disabled: 3 } as Record<string, number>;
  const sources = [...run.sources].sort((a, b) => order[a.status] - order[b.status] || a.name.localeCompare(b.name));
  const th = "px-2 py-2 text-left font-medium text-muted";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">{t.sources.title}</h1>
        <p className="mt-2 text-ink-2">{t.sources.intro}</p>
        <p className="mt-1 text-sm text-muted">{t.sources.tierHelp}</p>
      </div>

      <Card>
        <div className="-mx-4 overflow-x-auto sm:mx-0">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="border-b border-line">
              <tr>
                <th className={th}>{t.sources.cols.name}</th>
                <th className={th}>{t.sources.cols.tier}</th>
                <th className={th}>{t.sources.cols.status}</th>
                <th className={th}>{t.sources.cols.lastSuccess}</th>
                <th className={`${th} text-right`}>{t.sources.cols.items}</th>
                <th className={th}>{t.sources.cols.error}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {sources.map((s) => (
                <tr key={s.id} className="align-top">
                  <td className="px-2 py-2 font-medium">{s.name}</td>
                  <td className="px-2 py-2 tabular">{s.tier}</td>
                  <td className="px-2 py-2">
                    <StatusPill status={s.status} />
                  </td>
                  <td className="whitespace-nowrap px-2 py-2 text-ink-2">
                    {s.last_success ? fmtDateTime(s.last_success, locale) : t.never}
                  </td>
                  <td className="px-2 py-2 text-right tabular">{s.items}</td>
                  <td className="max-w-md px-2 py-2 text-xs text-muted">{s.error ?? s.note ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title={t.anchors}>
        {run.anchors.length === 0 ? (
          <Muted>–</Muted>
        ) : (
          <ul className="divide-y divide-line text-sm">
            {run.anchors.map((a) => (
              <li key={a.id} className="flex flex-wrap items-baseline gap-x-3 py-2">
                <span className="w-8 font-semibold">{a.country}</span>
                <a href={a.url} target="_blank" rel="noreferrer" className="font-medium">
                  {a.name}
                </a>
                <span>{a.raw ?? "–"}</span>
                {a.level && (
                  <span className="text-muted tabular">
                    {a.level}/{a.scale.length}
                  </span>
                )}
                <StatusPill status={a.status} />
                {a.as_of && <span className="text-xs text-muted">{fmtDate(a.as_of, locale)}</span>}
                {a.detail && <span className="w-full pl-11 text-xs text-muted">{a.detail}</span>}
                {a.error && <span className="w-full pl-11 text-xs text-level-4">{a.error}</span>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
