import type { ReactNode } from "react";

const TONES = {
  warning: "border-warning/50 bg-warning/10",
  success: "border-success/40 bg-success/10",
} as const;

/** A short notice above a page's content (a demo or simulation note, a result): one look everywhere. */
export function Note({ children, icon, tone = "warning", className }: { children: ReactNode; icon?: ReactNode; tone?: keyof typeof TONES; className?: string }) {
  return (
    <p role="note" className={`flex items-start gap-2 rounded-xl border px-4 py-2.5 text-sm ${TONES[tone]} ${className ?? ""}`}>
      {icon ? <span aria-hidden="true" className="mt-0.5 shrink-0 [&>svg]:size-4">{icon}</span> : null}
      <span className="min-w-0">{children}</span>
    </p>
  );
}
