import { ArticleLink, Muted } from "../components/ui";
import { useLang } from "../i18n";
import type { Tesat } from "../types/run";

/** Europol TE-SAT headline figures, with attacks by type as one-series bars. */
export function BaseRates({ tesat }: { tesat: Tesat | null }) {
  const { t } = useLang();
  if (!tesat) return <Muted>{t.baseRatesPending}</Muted>;
  const cur = tesat.current;
  const rows = Object.entries(tesat.attacks_by_ideology).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...rows.map(([, n]) => n), 1);
  return (
    <div className="space-y-5">
      <p className="text-sm text-muted">
        <ArticleLink href={tesat.url} className="text-link">
          {t.tesat.source(tesat.report_year, cur.data_year)}
        </ArticleLink>
      </p>
      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <div className="text-4xl font-bold tabular">{cur.attacks_total}</div>
          <div className="text-sm text-ink-2">{t.tesat.attacks}</div>
          <div className="mt-1 text-xs text-muted tabular">
            {t.tesat.split(cur.attacks_completed ?? 0, tesat.attacks_failed, tesat.attacks_foiled)}
          </div>
        </div>
        <div>
          <div className="text-4xl font-bold tabular">{cur.arrests_total}</div>
          <div className="text-sm text-ink-2">{t.tesat.arrests}</div>
        </div>
        <div>
          <div className="text-4xl font-bold tabular">{cur.fatalities ?? "–"}</div>
          <div className="text-sm text-ink-2">{t.tesat.deaths}</div>
        </div>
      </div>
      {tesat.previous && (
        <p className="text-sm text-muted tabular">
          {t.tesat.previous(tesat.previous.data_year, tesat.previous.attacks_total, tesat.previous.arrests_total)}
        </p>
      )}
      <div>
        <h3 className="mb-2 text-sm font-semibold">{t.tesat.byType}</h3>
        <ul className="space-y-2">
          {rows.map(([k, n]) => (
            <li key={k} className="grid grid-cols-[minmax(8rem,14rem)_1fr_2rem] items-center gap-3 text-sm">
              <span className="text-ink-2">{t.ideologies[k] ?? k}</span>
              <span className="h-3 rounded-r" style={{ width: `${(n / max) * 100}%`, background: "var(--series-1)" }} />
              <span className="text-right font-semibold tabular">{n}</span>
            </li>
          ))}
        </ul>
      </div>
      <p className="text-sm">{t.tesat.slovakia(tesat.slovakia_attacks, tesat.slovakia_arrests)}</p>
      <Muted>{t.tesat.gtdPending}</Muted>
    </div>
  );
}
