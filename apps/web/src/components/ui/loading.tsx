import type { ReactNode } from "react";

/** Three pulsing dots with a screen-reader label: for a button, a corner or a small area. */
export function LoadingDots({ label, className = "" }: { label: string; className?: string }) {
  return (
    <span role="status" className={`loading-dots ${className}`}>
      <span className="sr-only">{label}</span>
      <span aria-hidden="true" />
      <span aria-hidden="true" />
      <span aria-hidden="true" />
    </span>
  );
}

/** A thin bar. With `value` (0 to 100) it fills; without it, it slides back and forth. */
export function ProgressBar({ label, value }: { label: string; value?: number }) {
  const known = typeof value === "number";
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={known ? Math.round(value) : undefined}
      className="progress-bar"
      data-indeterminate={known ? undefined : true}
    >
      <span style={known ? { inlineSize: `${Math.min(100, Math.max(0, value))}%` } : undefined} />
    </div>
  );
}

/** Keeps the old content on screen while new data loads: it dims, shows dots in the middle and is
 * not clickable, instead of jumping to a blank page. Wrap a list or a chart that refetches. */
export function PendingContent({ pending, label, children }: { pending: boolean; label: string; children: ReactNode }) {
  return (
    <div className="pending-content" data-pending={pending || undefined} aria-busy={pending}>
      <div inert={pending}>{children}</div>
      {pending ? <LoadingDots label={label} className="pending-dots" /> : null}
    </div>
  );
}
