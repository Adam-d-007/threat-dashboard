import { marked } from "marked";
import { Card } from "../components/ui";
import { useLang } from "../i18n";
import scoring from "../../../docs/SCORING.md?raw";

// Links in SCORING.md are relative to the repository; on the site they point to GitHub.
const REPO = "https://github.com/Adam-d-007/threat-dashboard/blob/main/";
const html = marked.parse(scoring.replaceAll("](../", `](${REPO}`), { async: false });

export function MethodPage() {
  const { t } = useLang();
  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">{t.method.title}</h1>
      <Card>
        <div className="space-y-4 leading-relaxed text-ink-2">
          {t.method.body.map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>
      </Card>
      <Card title={t.fullMethod}>
        {/* Our own document, bundled at build time: not user content. */}
        <div className="method-doc" dangerouslySetInnerHTML={{ __html: html }} />
      </Card>
    </div>
  );
}
