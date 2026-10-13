"use client";

import { Moon, Sun } from "lucide-react";
import { useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

import { useCustomPalette } from "@/components/palette";

// True only after hydration; the stored theme is unknown on the server.
function useMounted() {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}

/** One click between light and dark (the sun/moon button in the marketing header and footer and
 * the CRM's top bar). It flips what the person currently sees, even when the stored choice is
 * "system". The three-way choice stays in the settings (ThemeSwitcher). Hidden for "my own
 * colors", whose background decides light or dark itself. */
export function ThemeToggle({ className = "" }: { className?: string }) {
  const t = useTranslations("settings");
  const { resolvedTheme, setTheme } = useTheme();
  const mounted = useMounted();
  const custom = useCustomPalette();
  if (custom) return null;

  const dark = mounted && resolvedTheme === "dark";
  const label = dark ? t("themeToggleToLight") : t("themeToggleToDark");
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={() => setTheme(dark ? "light" : "dark")}
      className={`flex size-10 items-center justify-center rounded-full border border-border bg-surface text-foreground/80 transition-colors hover:bg-foreground/5 hover:text-foreground ${className}`.trim()}
    >
      {/* Both icons render until hydration; CSS shows the right one (no flash on first paint). */}
      <Sun aria-hidden="true" className="size-[1.15rem] hidden dark:block" />
      <Moon aria-hidden="true" className="size-[1.15rem] dark:hidden" />
    </button>
  );
}
