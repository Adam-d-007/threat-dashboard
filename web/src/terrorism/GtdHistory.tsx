import { ArticleLink } from "../components/ui";
import { useLang } from "../i18n";
import type { Gtd } from "../types/run";

/** Incidents per year from the Global Terrorism Database, one column per year. */
export function GtdHistory({ gtd, region }: { gtd: Gtd; region: "SK" | "EU" }) {
  const { t, locale } = useLang();
  const years = gtd[region];
  // A year without data (1993: START lost those records) is a gap, never a zero.
  const known = years.filter((y) => y.incidents !== null);
  const max = Math.max(...known.map((y) => y.incidents!), 1);
  const peak = known.reduce((a, b) => (b.incidents! > a.incidents! ? b : a), known[0]);
  const total = known.reduce((n, y) => n + y.incidents!, 0);
  const missing = years.filter((y) => y.incidents === null).map((y) => y.year);
  return (
    <div>
      <h3 className="mb-1 text-sm font-semibold">{t.gtd.title(region === "SK" ? t.gtd.sk : t.gtd.eu)}</h3>
      <p className="mb-3 text-xs text-muted tabular">{t.gtd.summary(total, total.toLocaleString(locale), peak.year, peak.incidents!)}</p>
      <div className="flex h-24 items-end gap-px" role="img" aria-label={t.gtd.summary(total, total.toLocaleString(locale), peak.year, peak.incidents!)}>
        {years.map((y) =>
          y.incidents === null ? (
            <span key={y.year} title={t.gtd.noData(y.year)} className="h-full flex-1 rounded-t-sm border border-dashed border-line" />
          ) : (
            <span
              key={y.year}
              title={t.gtd.bar(y.year, y.incidents, y.deaths ?? 0)}
              className="flex-1 rounded-t-sm hover:opacity-70"
              style={{ height: `${(y.incidents / max) * 100}%`, minHeight: y.incidents ? 2 : 0, background: "var(--series-1)" }}
            />
          ),
        )}
      </div>
      <div className="mt-1 flex justify-between text-xs text-muted tabular">
        <span>{years[0].year}</span>
        <span>{years[years.length - 1].year}</span>
      </div>
      <p className="mt-2 text-xs text-muted">
        {t.gtd.ends(gtd.data_ends)} {missing.length > 0 && t.gtd.missing(missing.join(", "))}
      </p>
      {/* Citation and notice worded exactly as the GTD licence (section 4) requires. */}
      <p className="mt-1 text-xs text-muted">
        START (National Consortium for the Study of Terrorism and Responses to Terrorism). (2022). Global
        Terrorism Database, 1970 - 2020 [data file].{" "}
        <ArticleLink href="https://www.start.umd.edu/data-tools/GTD" className="text-link">
          https://www.start.umd.edu/data-tools/GTD
        </ArticleLink>{" "}
        Copyright University of Maryland 2022.
      </p>
    </div>
  );
}
