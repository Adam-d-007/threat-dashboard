import type { ReactNode } from "react";
import { useLang } from "../i18n";

export function Card({
  title,
  id,
  action,
  children,
  className = "",
}: {
  title?: ReactNode;
  id?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section id={id} className={`scroll-mt-24 rounded-xl border border-line bg-surface p-4 sm:p-5 ${className}`}>
      {(title || action) && (
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          {title && <h2 className="text-base font-semibold text-ink">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

const LEVEL_BG = ["bg-level-1", "bg-level-2", "bg-level-3", "bg-level-4"];
// Level 4 red is too dark for black text; the other three take dark ink.
const LEVEL_FG = ["text-black", "text-black", "text-black", "text-white"];

/** A threat level: always colour, number and word together. */
export function LevelBadge({ level, size = "md" }: { level: number; size?: "sm" | "md" | "xl" }) {
  const { t } = useLang();
  const i = level - 1;
  const box =
    size === "xl"
      ? "h-20 w-20 text-5xl sm:h-24 sm:w-24 sm:text-6xl rounded-2xl"
      : size === "md"
        ? "h-10 w-10 text-xl rounded-lg"
        : "h-6 w-6 text-sm rounded";
  return (
    <span className="inline-flex items-center gap-3">
      <span
        className={`inline-flex shrink-0 items-center justify-center font-bold tabular ${box} ${LEVEL_BG[i]} ${LEVEL_FG[i]}`}
        aria-hidden
      >
        {level}
      </span>
      {size !== "sm" ? (
        <span className={size === "xl" ? "text-2xl font-semibold sm:text-3xl" : "font-semibold"}>
          {t.levelNames[i]}
        </span>
      ) : (
        <span className="text-sm">{t.levelNames[i]}</span>
      )}
      <span className="sr-only">
        {t.levelWord} {level}
      </span>
    </span>
  );
}

export function Banner({ tone, children }: { tone: "info" | "warn" | "crit" | "sample"; children: ReactNode }) {
  const cls = {
    info: "border-line bg-surface-2 text-ink-2",
    warn: "border-level-2 bg-level-2/10 text-ink",
    crit: "border-level-4 bg-level-4/15 text-ink",
    sample: "border-sample bg-sample/15 text-ink font-semibold",
  }[tone];
  const icon = { info: "ℹ", warn: "⚠", crit: "⛔", sample: "✎" }[tone];
  return (
    <div role={tone === "info" ? "status" : "alert"} className={`flex gap-2 rounded-lg border px-3 py-2 text-sm ${cls}`}>
      <span aria-hidden>{icon}</span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

const STATUS_STYLE: Record<string, string> = {
  ok: "text-level-1",
  stale: "text-level-3",
  failed: "text-level-4",
  disabled: "text-muted",
};
const STATUS_ICON: Record<string, string> = { ok: "●", stale: "◐", failed: "✕", disabled: "○" };

export function StatusPill({ status }: { status: string }) {
  const { t } = useLang();
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap ${STATUS_STYLE[status]}`}>
      <span aria-hidden>{STATUS_ICON[status]}</span>
      <span className="text-ink-2">{t.sourceStatus[status]}</span>
    </span>
  );
}

export function Muted({ children }: { children: ReactNode }) {
  return <p className="text-sm text-muted">{children}</p>;
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex overflow-hidden rounded-lg border border-line text-sm">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={`px-3 py-1.5 ${value === o.value ? "bg-ink text-page font-semibold" : "text-ink-2 hover:bg-surface-2"}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
