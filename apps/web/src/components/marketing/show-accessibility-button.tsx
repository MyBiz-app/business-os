"use client";

import { useTranslations } from "next-intl";

import { showAccessibilityWidget } from "@/components/accessibility-widget";

/** Footer link that brings the floating accessibility button back after it was closed. */
export function ShowAccessibilityButton() {
  const t = useTranslations("accessibility");
  return (
    <button type="button" onClick={showAccessibilityWidget} className="btn-link text-xs text-white/65 underline-offset-2 transition-colors hover:text-white hover:underline">
      {t("widgetShow")}
    </button>
  );
}
