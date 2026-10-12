"use client";

import { useTranslations } from "next-intl";

/** The first tab stop on every page: jumps keyboard and screen-reader users past the menu to the page's <main>. */
export function SkipLink() {
  const t = useTranslations("common");
  return (
    <a
      href="#main"
      onClick={(event) => {
        const main = document.querySelector("main");
        if (!main) return;
        event.preventDefault();
        main.setAttribute("tabindex", "-1");
        main.focus();
        main.scrollIntoView();
      }}
      className="sr-only focus:not-sr-only focus:fixed focus:start-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-on-primary"
    >
      {t("skipToContent")}
    </a>
  );
}
