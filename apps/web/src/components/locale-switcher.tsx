"use client";

import { Check, ChevronDown, Languages } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useCallback, useId, useRef, useState, useTransition } from "react";

import { setLocale } from "@/i18n/actions";
import { locales } from "@/i18n/config";
import { moveFocus, useDismiss } from "@/components/use-dismiss";

/** The language menu: a compact button that opens a small list under (or, near the bottom of the
 * screen, above) it. Same look as the profile menu. */
export function LocaleSwitcher() {
  const t = useTranslations();
  const current = useLocale();
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [open, setOpen] = useState(false);
  const [up, setUp] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close, root, button);

  const toggle = () => {
    if (!open && button.current) {
      const rect = button.current.getBoundingClientRect();
      const below = window.innerHeight - rect.bottom;
      setUp(below < 160 && rect.top > below);
    }
    setOpen((value) => !value);
  };

  const choose = (next: string) => {
    close();
    button.current?.focus();
    if (next === current) return;
    startTransition(async () => {
      await setLocale(next);
      router.refresh();
    });
  };

  return (
    <div ref={root} className="relative">
      <button
        ref={button}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        disabled={pending}
        onClick={toggle}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setOpen(true);
            requestAnimationFrame(() => document.getElementById(menuId)?.querySelector<HTMLElement>("[role=menuitemradio]")?.focus());
          }
        }}
        className="flex h-9 items-center gap-1.5 rounded-full px-2.5 text-sm font-medium transition-colors hover:bg-foreground/5 aria-expanded:bg-foreground/5 disabled:opacity-60"
      >
        <Languages aria-hidden="true" className="size-4 text-muted" />
        <span aria-hidden="true">{t(`locales.${current}`)}</span>
        <ChevronDown aria-hidden="true" className={`size-3.5 text-muted transition-transform ${open ? "rotate-180" : ""}`} />
        <span className="sr-only">{t("settings.language")}</span>
      </button>
      <div
        id={menuId}
        role="menu"
        aria-label={t("settings.language")}
        onKeyDown={(event) => moveFocus(event, "[role=menuitemradio]")}
        data-open={open}
        className={`popover absolute end-0 z-40 w-40 p-1.5 ${up ? "bottom-full mb-2 origin-bottom-right rtl:origin-bottom-left" : "top-full mt-2 origin-top-right rtl:origin-top-left"}`}
      >
        {locales.map((locale) => (
          <button
            key={locale}
            type="button"
            role="menuitemradio"
            aria-checked={locale === current}
            onClick={() => choose(locale)}
            className="flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-sm outline-none transition-colors hover:bg-foreground/5 focus-visible:bg-foreground/5 aria-checked:font-semibold"
          >
            {t(`locales.${locale}`)}
            {locale === current && <Check aria-hidden="true" className="size-4 text-primary" />}
          </button>
        ))}
      </div>
    </div>
  );
}
