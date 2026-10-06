const DOT = {
  success: "bg-success",
  primary: "bg-primary",
  warning: "bg-warning",
  danger: "bg-danger",
  muted: "bg-muted",
} as const;

export type Tone = keyof typeof DOT;

/** A status label. Text stays in the foreground color (always readable); the dot carries the
 * status color, so meaning never depends on colored text alone. */
export function Pill({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-surface px-2.5 py-0.5 text-xs font-medium ring-1 ring-border">
      <span aria-hidden="true" className={`size-1.5 shrink-0 rounded-full ${DOT[tone]}`} />
      {children}
    </span>
  );
}
