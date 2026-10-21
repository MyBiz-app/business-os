"use client";

import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

import { FORM_SAVED_EVENT } from "./form-message";
import { SubmitButton } from "./submit-button";

/**
 * The save action of a settings form: nothing shows until a field changes, then a bar rests at the
 * bottom of the screen with "Discard" and "Save". Put it as the last child of the `<form>`; it
 * watches that form, and goes away again when the form has saved or the changes are discarded.
 */
export function SaveBar() {
  const t = useTranslations("common");
  const marker = useRef<HTMLSpanElement>(null);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    const form = marker.current?.closest("form");
    if (!form) return;
    const change = () => setDirty(true);
    const clear = () => setDirty(false);
    form.addEventListener("input", change);
    form.addEventListener("change", change);
    form.addEventListener("reset", clear);
    form.addEventListener(FORM_SAVED_EVENT, clear);
    return () => {
      form.removeEventListener("input", change);
      form.removeEventListener("change", change);
      form.removeEventListener("reset", clear);
      form.removeEventListener(FORM_SAVED_EVENT, clear);
    };
  }, []);

  return (
    <>
      <span ref={marker} hidden />
      {/* Room under the last group, so the bar never covers it. */}
      {dirty && <div aria-hidden="true" className="h-16 print:hidden" />}
      <div
        role="region"
        aria-label={t("unsavedChanges")}
        aria-hidden={!dirty}
        inert={!dirty}
        data-open={dirty || undefined}
        className="save-bar fixed inset-x-0 bottom-0 z-30 flex justify-center px-4 pb-[max(1rem,env(safe-area-inset-bottom))] print:hidden"
      >
        <div className="flex w-full max-w-xl items-center justify-between gap-3 rounded-2xl border border-border bg-surface/95 py-2.5 ps-4 pe-2.5 shadow-lg backdrop-blur">
          <p className="min-w-0 text-sm font-medium">{t("unsavedChanges")}</p>
          <div className="flex shrink-0 items-center gap-1.5">
            <Button variant="quiet" onClick={() => marker.current?.closest("form")?.reset()}>
              {t("discardChanges")}
            </Button>
            <SubmitButton className="px-4 py-2">{t("save")}</SubmitButton>
          </div>
        </div>
      </div>
    </>
  );
}
