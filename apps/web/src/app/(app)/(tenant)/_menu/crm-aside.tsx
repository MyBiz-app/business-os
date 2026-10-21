"use client";

import { PanelLeft } from "lucide-react";
import { useState, type ReactNode } from "react";

export type NavTone = "dark" | "light";

export const NAV_TONE_COOKIE = "nav_tone";

/** The CRM's navigation column. It is light by default (Calm); in light mode a person can switch
 * to a dark column (the choice is kept in a cookie, so the server renders it without a flash).
 * In night mode the column takes the night surface, so the switch is hidden there. */
export function CrmAside({ initial, labels, children }: { initial: NavTone; labels: { light: string; dark: string }; children: ReactNode }) {
  const [tone, setTone] = useState<NavTone>(initial);
  const next: NavTone = tone === "dark" ? "light" : "dark";

  const choose = () => {
    setTone(next);
    document.cookie = `${NAV_TONE_COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
  };

  return (
    <aside className={`${tone === "light" ? "nav-light" : "nav-dark"} print:hidden max-md:border-b max-md:border-border md:sticky md:top-16 md:flex md:h-[calc(100dvh-4rem)] md:w-64 md:shrink-0 md:flex-col md:overflow-y-auto`}>
      {children}
      <button
        type="button"
        onClick={choose}
        className="btn-plain nav-tone-switch mx-3 mb-3 mt-auto hidden items-center gap-2 rounded-xl px-3 py-2 text-xs font-medium text-muted transition-colors hover:text-foreground md:flex dark:md:hidden"
      >
        <PanelLeft aria-hidden="true" className="size-4" />
        {tone === "dark" ? labels.light : labels.dark}
      </button>
    </aside>
  );
}
