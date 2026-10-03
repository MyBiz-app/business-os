"use client";

import { useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

const themes = ["light", "dark", "system"] as const;
const labelKeys = { light: "themeLight", dark: "themeDark", system: "themeSystem" } as const;

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

  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-muted">{t("theme")}</span>
      <select
        className="rounded-md border border-border bg-surface px-2 py-1"
        value={mounted ? theme : "system"}
        onChange={(event) => setTheme(event.target.value)}
      >
        {themes.map((value) => (
          <option key={value} value={value}>
            {t(labelKeys[value])}
          </option>
        ))}
      </select>
    </label>
  );
}
