"use client";

import { useTranslations } from "next-intl";

import { OPEN_EVENT } from "@/components/ui/collapsible-section";

export type AccountMenuItem = { id: string; label: string };

/** The profile's section menu: a click opens that section and scrolls to it smoothly. */
export function AccountMenu({ items }: { items: AccountMenuItem[] }) {
  const t = useTranslations("account");

  function go(event: React.MouseEvent<HTMLAnchorElement>, id: string) {
    event.preventDefault();
    window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: id }));
    window.history.replaceState(null, "", `#${id}`);
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // The section unfolds while it scrolls, so wait a frame for it to take its place.
    requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ behavior: calm ? "auto" : "smooth", block: "start" }));
  }

  return (
    <nav aria-label={t("nav.label")} className="hidden flex-col gap-0.5 print:hidden lg:sticky lg:top-24 lg:flex">
      {items.map((item) => (
        <a
          key={item.id}
          href={`#${item.id}`}
          onClick={(event) => go(event, item.id)}
          className="rounded-xl px-3 py-2.5 text-sm text-foreground transition-colors hover:bg-foreground/5"
        >
          {item.label}
        </a>
      ))}
    </nav>
  );
}
