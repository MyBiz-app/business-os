"use client";

import { Menu, Sparkles, X } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { ThemeSwitcher } from "@/components/theme-switcher";

const LINKS = [
  { href: "/features", key: "features" },
  { href: "/industries/fitness", key: "industries", match: "/industries" },
  { href: "/pricing", key: "pricing" },
  { href: "/about", key: "about" },
  { href: "/contact", key: "contact" },
] as const;

/** The marketing site's header: navigation, language and theme, and the two calls to action. */
export function MarketingHeader() {
  const t = useTranslations("marketing.nav");
  const tApp = useTranslations("app");
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const links = LINKS.map((link) => {
    const active = pathname.startsWith("match" in link ? link.match : link.href);
    return (
      <Link
        key={link.href}
        href={link.href}
        aria-current={active ? "page" : undefined}
        onClick={() => setOpen(false)}
        className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
          active ? "text-primary" : "text-muted hover:bg-foreground/5 hover:text-foreground"
        }`}
      >
        {t(link.key)}
      </Link>
    );
  });

  return (
    <header className="sticky top-0 z-30 border-b border-border/70 bg-background/75 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-6">
        <Link href="/" className="group flex items-center gap-2 text-lg font-bold">
          <span
            aria-hidden="true"
            className="flex size-8 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-fuchsia-500 text-white shadow-md transition-transform duration-300 group-hover:rotate-12"
          >
            <Sparkles className="size-4" />
          </span>
          {tApp("name")}
        </Link>

        <nav aria-label={t("menu")} className="hidden items-center gap-1 lg:flex">
          {links}
        </nav>

        <div className="hidden items-center gap-2 lg:flex">
          <LocaleSwitcher />
          <ThemeSwitcher />
          <Link href="/login" className="rounded-lg px-3 py-2 text-sm font-semibold hover:bg-foreground/5">
            {t("login")}
          </Link>
          <Link href="/signup" className="btn-primary px-4 py-2 text-sm">
            {t("start")}
          </Link>
        </div>

        <button
          type="button"
          className="flex size-10 items-center justify-center rounded-xl border border-border lg:hidden"
          aria-expanded={open}
          aria-controls="marketing-menu"
          aria-label={open ? t("close") : t("menu")}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X aria-hidden="true" className="size-5" /> : <Menu aria-hidden="true" className="size-5" />}
        </button>
      </div>

      {open && (
        <div id="marketing-menu" className="border-t border-border bg-background px-6 py-4 lg:hidden">
          <nav aria-label={t("menu")} className="flex flex-col gap-1">
            {links}
          </nav>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <LocaleSwitcher />
            <ThemeSwitcher />
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <Link href="/login" className="btn-secondary px-4 py-2.5">
              {t("login")}
            </Link>
            <Link href="/signup" className="btn-primary px-4 py-2.5">
              {t("start")}
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
