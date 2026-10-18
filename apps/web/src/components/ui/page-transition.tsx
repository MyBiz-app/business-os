import { type ReactNode, ViewTransition } from "react";

/** Page content that fades in when the route changes (use it in a `template.tsx`, which remounts on
 * every navigation; a layout persists, so enter and exit would never fire there). `kind` picks the
 * motion in globals.css: "site" fades and slides up a little (landing), "app" only fades (CRM).
 * Browsers without view transitions, and people who asked for less motion, get a plain swap. */
export function PageTransition({ kind, children }: { kind: "site" | "app"; children: ReactNode }) {
  return (
    <ViewTransition enter={`vt-${kind}-in`} exit={`vt-${kind}-out`} default="none">
      {children}
    </ViewTransition>
  );
}

/** A card in a list that grows into the window opened from it (`RouteModal transitionName`) and
 * shrinks back when the window closes. The name must be unique on the page, e.g. `lead-<id>`. */
export function CardTransition({ name, children }: { name: string; children: ReactNode }) {
  return (
    <ViewTransition name={name} share="card-window" default="none">
      {children}
    </ViewTransition>
  );
}
