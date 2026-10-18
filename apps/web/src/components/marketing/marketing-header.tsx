"use client";

import { Menu, X } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useRef, useState } from "react";

import { Container } from "@/components/layout/container";
import { BrandMark } from "@/components/brand-mark";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { ThemeToggle } from "@/components/theme-toggle";
import { moveFocus, useDismiss } from "@/components/use-dismiss";

const LINKS = [
  { href: "/features", key: "features" },
  { href: "/industries/fitness", key: "industries", match: "/industries" },
<<<<<<< HEAD
  { href: "/ai-team", key: "aiTeam" },
=======
  { href: "/websites", key: "websites" },
>>>>>>> origin/main
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
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close, root, button);

  const links = LINKS.map((link) => {
    const active = pathname.startsWith("match" in link ? link.match : link.href);
    return (
      <Link
        key={link.href}
        href={link.href}
        aria-current={active ? "page" : undefined}
        onClick={() => setOpen(false)}
        className={`rounded-lg px-3 py-2.5 text-sm font-semibold transition-colors ${
          active ? "text-primary-ink" : "text-foreground/70 hover:bg-foreground/5 hover:text-foreground"
        }`}
      >
        {t(link.key)}
      </Link>
    );
  });

  return (
    <header className="sticky top-0 z-30 border-b border-border/70 bg-surface/80 backdrop-blur-xl" style={{ viewTransitionName: "mk-header" }}>
      <Container className="flex h-16 items-center justify-between gap-4">
        <Link href="/" className="group flex items-center gap-2 text-lg font-bold">
          <BrandMark className="size-8 drop-shadow-md transition-transform duration-300 group-hover:rotate-12" />
          {tApp("name")}
        </Link>

        <nav aria-label={t("menu")} className="hidden items-center gap-1 lg:flex">
          {links}
        </nav>

        <div className="hidden items-center gap-2 lg:flex">
          <LocaleSwitcher />
          <ThemeToggle />
          <Link href="/login" className="rounded-lg px-3 py-2 text-sm font-semibold hover:bg-foreground/5">
            {t("login")}
          </Link>
          <Link href="/start" className="btn-primary rounded-full px-5 py-2 text-sm">
            {t("start")}
          </Link>
        </div>

        <div ref={root} className="relative lg:hidden">
          <button
            ref={button}
            type="button"
            className="btn-icon flex size-10 items-center justify-center rounded-xl border border-border transition-colors hover:bg-foreground/5 aria-expanded:bg-foreground/5"
            aria-expanded={open}
            aria-controls="marketing-menu"
            aria-label={open ? t("close") : t("menu")}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X aria-hidden="true" className="size-5" /> : <Menu aria-hidden="true" className="size-5" />}
          </button>
          <div
            id="marketing-menu"
            data-open={open}
            onKeyDown={(event) => moveFocus(event)}
            className="popover absolute end-0 top-full z-40 mt-2 w-[min(20rem,calc(100vw-2rem))] origin-top-right p-2 rtl:origin-top-left"
          >
            <nav aria-label={t("menu")} className="flex flex-col gap-0.5">
              {links}
            </nav>
            <div className="mt-2 flex items-center justify-between gap-3 border-t border-border px-1 pt-3">
              <LocaleSwitcher />
              <ThemeToggle />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 px-1 pb-1">
              <Link href="/login" onClick={close} className="btn-secondary px-4 py-2.5">
                {t("login")}
              </Link>
              <Link href="/start" onClick={close} className="btn-primary px-4 py-2.5">
                {t("start")}
              </Link>
            </div>
          </div>
        </div>
      </Container>
    </header>
  );
}
