"use client";

import { useTranslations } from "next-intl";
import { useSyncExternalStore } from "react";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { ThemeSwitcher } from "@/components/theme-switcher";

/** Display choices that help reading, kept on this device and set on <html> as data attributes
 * (see the `data-contrast`, `data-text` and `data-motion` rules in globals.css). The inline
 * script in palette-script.tsx applies them before the first paint. */
export const A11Y_KEY = "a11y";
type Prefs = { contrast: "normal" | "high"; text: "normal" | "large" | "larger"; motion: "normal" | "reduce" };
const DEFAULTS: Prefs = { contrast: "normal", text: "normal", motion: "normal" };

function read(): string {
  try {
    return localStorage.getItem(A11Y_KEY) ?? "";
  } catch {
    return "";
  }
}

function parse(raw: string): Prefs {
  try {
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return DEFAULTS;
  }
}

function subscribe(notify: () => void) {
  window.addEventListener("storage", notify);
  window.addEventListener("a11y-change", notify);
  return () => {
    window.removeEventListener("storage", notify);
    window.removeEventListener("a11y-change", notify);
  };
}

function save(prefs: Prefs) {
  const root = document.documentElement;
  for (const [key, value] of Object.entries(prefs)) {
    if (value === "normal") delete root.dataset[key];
    else root.dataset[key] = value;
  }
  try {
    localStorage.setItem(A11Y_KEY, JSON.stringify(prefs));
  } catch {
    // private browsing: the choice still applies until the page is closed
  }
  window.dispatchEvent(new Event("a11y-change"));
}

function Choice<T extends string>({
  label,
  hint,
  value,
  options,
  onChange,
}: {
  label: string;
  hint: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <Row label={label} hint={hint}>
      <div role="group" aria-label={label} className="flex items-center gap-0.5 rounded-xl border border-border bg-surface p-0.5">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={value === option.value}
            onClick={() => onChange(option.value)}
            className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
              value === option.value ? "bg-primary/12 font-medium text-primary" : "text-muted hover:text-foreground"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </Row>
  );
}

function Row({ label, hint, children }: { label: string; hint: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-border pt-4 first:border-t-0 first:pt-0">
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="text-sm font-medium">{label}</span>
        <span className="text-xs text-muted">{hint}</span>
      </div>
      {children}
    </div>
  );
}

/** Language, theme, contrast, text size and motion: the choices that used to sit in the toolbar. */
export function AccessibilitySettings() {
  const t = useTranslations("accessibility");
  const prefs = parse(useSyncExternalStore(subscribe, read, () => ""));
  const set = (patch: Partial<Prefs>) => save({ ...prefs, ...patch });

  return (
    <div className="flex flex-col gap-4">
      <Row label={t("language")} hint={t("languageHint")}>
        <LocaleSwitcher />
      </Row>
      <Row label={t("theme")} hint={t("themeHint")}>
        <ThemeSwitcher />
      </Row>
      <Choice
        label={t("contrast")}
        hint={t("contrastHint")}
        value={prefs.contrast}
        onChange={(contrast) => set({ contrast })}
        options={[
          { value: "normal", label: t("contrastNormal") },
          { value: "high", label: t("contrastHigh") },
        ]}
      />
      <Choice
        label={t("textSize")}
        hint={t("textSizeHint")}
        value={prefs.text}
        onChange={(text) => set({ text })}
        options={[
          { value: "normal", label: t("textNormal") },
          { value: "large", label: t("textLarge") },
          { value: "larger", label: t("textLarger") },
        ]}
      />
      <Choice
        label={t("motion")}
        hint={t("motionHint")}
        value={prefs.motion}
        onChange={(motion) => set({ motion })}
        options={[
          { value: "normal", label: t("textNormal") },
          { value: "reduce", label: t("motionReduced") },
        ]}
      />
    </div>
  );
}
