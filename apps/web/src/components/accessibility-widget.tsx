"use client";

import { Accessibility, X } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useCallback, useId, useRef, useState } from "react";

import { AccessibilitySettings, resetAccessibility } from "@/components/accessibility";
import { useDismiss } from "@/components/use-dismiss";

/** The floating accessibility button every public page and sign-in screen carries: language, day or night,
 * contrast, text size and motion in one panel, plus the accessibility statement. */
export function AccessibilityWidget() {
  const t = useTranslations("accessibility");
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close, root, trigger);

  return (
    <div ref={root} className="fixed bottom-5 start-5 z-40 print:hidden">
      {open && (
        <section
          id={panelId}
          role="dialog"
          aria-label={t("widgetTitle")}
          className="popover absolute bottom-16 start-0 flex max-h-[70vh] w-[min(24rem,calc(100vw-2.5rem))] flex-col gap-4 overflow-y-auto p-5"
          data-open="true"
        >
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-bold">{t("widgetTitle")}</h2>
            <button type="button" onClick={() => { close(); trigger.current?.focus(); }} aria-label={t("widgetClose")} className="btn-ghost size-8">
              <X aria-hidden="true" className="size-4" />
            </button>
          </div>
          <AccessibilitySettings />
          <div className="flex items-center justify-between gap-3 border-t border-border pt-4 text-sm">
            <button type="button" onClick={resetAccessibility} className="font-semibold text-primary hover:underline">
              {t("reset")}
            </button>
            <Link href="/legal/accessibility" className="font-semibold text-primary hover:underline">
              {t("statement")}
            </Link>
          </div>
        </section>
      )}
      <button
        ref={trigger}
        type="button"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-label={t("widgetOpen")}
        title={t("widgetOpen")}
        onClick={() => setOpen((value) => !value)}
        className="flex size-14 items-center justify-center rounded-full bg-primary text-on-primary shadow-lg shadow-primary/30 ring-4 ring-white/70 transition-transform duration-200 hover:scale-105 active:scale-95 dark:ring-black/40"
      >
        <Accessibility aria-hidden="true" className="size-7" />
      </button>
    </div>
  );
}
