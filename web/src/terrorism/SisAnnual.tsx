import { ArticleLink } from "../components/ui";
import { useLang } from "../i18n";
import type { SisAnnual } from "../types/run";

/** The SIS annual report's view of terrorism and extremism in Slovakia, summarised by hand. */
export function SisAnnualPoints({ sis }: { sis: SisAnnual }) {
  const { t, lang, locale } = useLang();
  const published = new Date(`${sis.published}-01T00:00:00Z`).toLocaleDateString(locale, {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
  const points = lang === "sk" ? sis.points_sk : sis.points_en;
  return (
    <div className="space-y-3">
      <ul className="list-disc space-y-2 pl-5 text-ink-2">
        {points.map((p, i) => (
          <li key={i}>{p}</li>
        ))}
      </ul>
      <p className="text-xs text-muted">
        <ArticleLink href={sis.url} className="text-link">
          {t.sisAnnual.source(sis.report_year, published)}
        </ArticleLink>{" "}
        {t.sisAnnual.note}
      </p>
    </div>
  );
}
