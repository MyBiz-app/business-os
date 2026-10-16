import type { ReactNode } from "react";

export type EmptyVariant = "calendar" | "people" | "list" | "chart" | "inbox";

/** A friendly empty state: a small animated illustration (in the brand colors, decorative only)
 * above the message. The motion is gentle and stops for reduced motion. */
export function EmptyState({ variant = "list", children, className = "" }: { variant?: EmptyVariant; children: ReactNode; className?: string }) {
  return (
    <div role="status" className={`flex flex-col items-center gap-4 rounded-2xl border border-dashed border-border p-10 text-center text-muted ${className}`}>
      <svg aria-hidden="true" viewBox="0 0 96 72" className="es-bob h-20 w-auto" fill="none">
        <ellipse cx="48" cy="66" rx="30" ry="3.5" className="fill-foreground/10" />
        {variant === "calendar" && (
          <>
            <rect x="20" y="12" width="56" height="48" rx="8" className="fill-surface stroke-primary" strokeWidth="2.5" />
            <path d="M20 26h56" className="stroke-primary" strokeWidth="2.5" />
            <path d="M34 8v10M62 8v10" className="stroke-electric" strokeWidth="3" strokeLinecap="round" />
            <rect x="30" y="34" width="10" height="8" rx="2" className="es-pulse fill-primary" />
            <rect x="46" y="34" width="10" height="8" rx="2" className="es-pulse fill-ai" style={{ animationDelay: "0.4s" }} />
            <rect x="30" y="46" width="10" height="8" rx="2" className="es-pulse fill-electric" style={{ animationDelay: "0.8s" }} />
          </>
        )}
        {variant === "people" && (
          <>
            <circle cx="48" cy="26" r="11" className="fill-surface stroke-primary" strokeWidth="2.5" />
            <path d="M26 58c0-12 9-19 22-19s22 7 22 19" className="fill-surface stroke-primary" strokeWidth="2.5" strokeLinecap="round" />
            <circle cx="76" cy="18" r="9" className="es-pulse fill-ai/80" />
            <path d="M76 14v8M72 18h8" stroke="white" strokeWidth="2" strokeLinecap="round" />
          </>
        )}
        {variant === "chart" && (
          <>
            <path d="M18 12v46h64" className="stroke-border" strokeWidth="2.5" strokeLinecap="round" />
            <rect x="28" y="38" width="10" height="20" rx="2" className="loop-bar fill-primary" />
            <rect x="46" y="28" width="10" height="30" rx="2" className="loop-bar fill-ai" style={{ animationDelay: "0.25s" }} />
            <rect x="64" y="18" width="10" height="40" rx="2" className="loop-bar fill-electric" style={{ animationDelay: "0.5s" }} />
          </>
        )}
        {variant === "inbox" && (
          <>
            <path d="M16 38l10-22h44l10 22v16a4 4 0 0 1-4 4H20a4 4 0 0 1-4-4V38z" className="fill-surface stroke-primary" strokeWidth="2.5" strokeLinejoin="round" />
            <path d="M16 38h20l4 8h16l4-8h20" className="stroke-primary" strokeWidth="2.5" strokeLinejoin="round" />
            <path d="M40 26l6 6 12-12" pathLength="1" className="es-draw stroke-success" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          </>
        )}
        {variant === "list" && (
          <>
            <rect x="22" y="8" width="52" height="54" rx="8" className="fill-surface stroke-primary" strokeWidth="2.5" />
            <path d="M34 24h28M34 36h28M34 48h16" pathLength="1" className="es-draw stroke-electric" strokeWidth="3" strokeLinecap="round" />
          </>
        )}
      </svg>
      <div className="max-w-prose">{children}</div>
    </div>
  );
}
