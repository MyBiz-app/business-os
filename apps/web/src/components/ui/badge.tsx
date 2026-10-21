import type { ReactNode } from "react";

import { cx } from "./cx";

export type BadgeTone = "neutral" | "primary" | "success" | "warning" | "danger" | "info";

const BADGE: Record<BadgeTone, string> = {
  neutral: "bg-subtle text-muted",
  primary: "bg-primary-subtle text-primary-ink",
  success: "bg-success-soft text-success-ink",
  warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger",
  info: "bg-info-soft text-info-ink",
};

const DOT: Record<BadgeTone, string> = {
  neutral: "bg-muted",
  primary: "bg-primary",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info-ink",
};

/** A short status or count in a soft tint (a light background with dark text). The words carry the
 * meaning; the color only supports them. */
export function Badge({ tone = "neutral", dot = false, children, className }: { tone?: BadgeTone; dot?: boolean; children: ReactNode; className?: string }) {
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap", BADGE[tone], className)}>
      {dot && <span aria-hidden="true" className={cx("size-1.5 shrink-0 rounded-full", DOT[tone])} />}
      {children}
    </span>
  );
}

/** A colored dot with its meaning in words: visible next to it, or only for screen readers when
 * `hideLabel` is set (a dot on an avatar or in a dense row). Color is never the only signal. */
export function StatusDot({ tone = "neutral", label, hideLabel = false, className }: { tone?: BadgeTone; label: string; hideLabel?: boolean; className?: string }) {
  return (
    <span className={cx("inline-flex items-center gap-1.5", className)}>
      <span aria-hidden="true" className={cx("size-2 shrink-0 rounded-full", DOT[tone])} />
      <span className={hideLabel ? "sr-only" : "text-sm"}>{label}</span>
    </span>
  );
}
