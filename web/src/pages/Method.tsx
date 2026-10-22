import { Card } from "../components/ui";
import { useLang } from "../i18n";

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
      <Card title={t.components}>
        <dl className="space-y-3 text-sm">
          {Object.entries(t.componentNames).map(([id, name]) => (
            <div key={id}>
              <dt className="font-semibold">{name}</dt>
              <dd className="text-ink-2">{t.componentHelp[id]}</dd>
            </div>
          ))}
        </dl>
      </Card>
    </div>
  );
}
