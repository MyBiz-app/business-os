"use client";

import { Lock, Monitor, Moon, Sun } from "lucide-react";
import { useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

import { useCustomPalette } from "@/components/palette";

const themes = [
  { value: "light", label: "themeLight", Icon: Sun },
  { value: "dark", label: "themeDark", Icon: Moon },
  { value: "system", label: "themeSystem", Icon: Monitor },
] as const;

// True only after hydration; the stored theme is unknown on the server.
function useMounted() {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}

export function ThemeSwitcher() {
  const t = useTranslations("settings");
  const { theme, setTheme } = useTheme();
  const mounted = useMounted();
  const current = mounted ? theme : "system";
  const custom = useCustomPalette();

  // "My own colors" decide light or dark themselves (by the background); see components/palette.tsx.
  if (custom) {
    return (
      <span className="flex items-center gap-1.5 rounded-xl border border-border bg-surface px-2.5 py-1.5 text-xs text-muted">
        <Lock aria-hidden="true" className="size-3.5" />
        {t("themeFollowsColors")}
      </span>
    );
  }

  return (
    <div role="group" aria-label={t("theme")} className="flex items-center gap-0.5 rounded-xl border border-border bg-surface p-0.5">
      {themes.map(({ value, label, Icon }) => (
        <button
          key={value}
          type="button"
          aria-label={t(label)}
          aria-pressed={current === value}
          title={t(label)}
          onClick={() => setTheme(value)}
          className={`flex size-7 items-center justify-center rounded-lg transition-colors sm:size-8 ${
            current === value ? "bg-primary/12 text-primary" : "text-muted hover:text-foreground"
          }`}
        >
          <Icon aria-hidden="true" className="size-4" />
        </button>
      ))}
    </div>
  );
}
