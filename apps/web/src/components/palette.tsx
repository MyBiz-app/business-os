"use client";

import { Check, Lock, TriangleAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { useEffect, useState, useSyncExternalStore, useTransition } from "react";

import { type DerivedTheme, deriveTheme, DEFAULT_COLORS, HEX, type PaletteColors } from "@/lib/palette-colors";

export const PALETTES = ["mybiz", "ocean", "forest", "custom"] as const;
export type Palette = (typeof PALETTES)[number];
export const PALETTE_KEY = "palette";
/** The derived colors of "my own colors", kept so the next page paints with them at once. */
export const CUSTOM_KEY = "palette-custom";
const THEME_BEFORE_KEY = "theme-before-custom";

function remember(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // private browsing: the account still keeps it
  }
}

function recall(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function clearCustom(root: HTMLElement) {
  for (const name of Object.keys(deriveTheme(DEFAULT_COLORS).tokens)) root.style.removeProperty(name);
}

/** Paints the page with a palette. "My own colors" set the derived colors on <html> and fix the
 * light/dark mode to the background's; leaving them restores the person's own mode. */
function apply(palette: Palette, colors: PaletteColors | null, setTheme: (theme: string) => void) {
  const root = document.documentElement;
  const wasCustom = root.dataset.palette === "custom";
  if (palette === "custom") {
    const derived: DerivedTheme = deriveTheme(colors ?? DEFAULT_COLORS);
    root.dataset.palette = "custom";
    for (const [name, value] of Object.entries(derived.tokens)) root.style.setProperty(name, value);
    if (!wasCustom) remember(THEME_BEFORE_KEY, recall("theme") ?? "system");
    setTheme(derived.scheme);
    remember(CUSTOM_KEY, JSON.stringify({ scheme: derived.scheme, tokens: derived.tokens }));
  } else {
    clearCustom(root);
    if (palette === "mybiz") delete root.dataset.palette;
    else root.dataset.palette = palette;
    remember(CUSTOM_KEY, null);
    if (wasCustom) {
      setTheme(recall(THEME_BEFORE_KEY) ?? "system");
      remember(THEME_BEFORE_KEY, null);
    }
  }
  remember(PALETTE_KEY, palette);
}

/** Follows the palette saved on the account (another device may have changed it). */
export function PaletteSync({ palette, colors }: { palette: Palette | null; colors: PaletteColors | null }) {
  const { setTheme } = useTheme();
  useEffect(() => {
    if (palette) apply(palette, colors, setTheme);
  }, [palette, colors, setTheme]);
  return null;
}

/** True while "my own colors" are on: they fix light or dark to match the background. */
export function useCustomPalette(): boolean {
  return useSyncExternalStore(
    (notify) => {
      const observer = new MutationObserver(notify);
      observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-palette"] });
      return () => observer.disconnect();
    },
    () => document.documentElement.dataset.palette === "custom",
    () => false,
  );
}

// The swatches show each palette's own colors, whatever the current one is.
const SWATCHES: Record<Exclude<Palette, "custom">, { light: string; ink: string; accent: string }> = {
  mybiz: { light: "#ffffff", ink: "#0a0a0a", accent: "#6d28d9" },
  ocean: { light: "#f4f7f9", ink: "#0b1a22", accent: "#0e7490" },
  forest: { light: "#f5f7f4", ink: "#0f1611", accent: "#166534" },
};

const PICKS = ["background", "text", "accent"] as const;

/** One of the three picks: a color well and its hex code, which can be typed or pasted. */
function ColorPick({ label, value, onChange }: { label: string; value: string; onChange: (hex: string) => void }) {
  const [typed, setTyped] = useState<string | null>(null); // what is being typed, until the field loses focus
  return (
    <label className="flex items-center gap-3 rounded-xl border border-border bg-surface p-2.5">
      <input
        type="color"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="size-10 shrink-0 cursor-pointer rounded-lg border border-border bg-transparent p-0.5"
      />
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-sm font-medium">{label}</span>
        <input
          type="text"
          value={typed ?? value}
          dir="ltr"
          maxLength={7}
          spellCheck={false}
          autoComplete="off"
          aria-label={label}
          onChange={(event) => {
            const text = event.target.value;
            setTyped(text);
            const hex = (text.startsWith("#") ? text : `#${text}`).toLowerCase();
            if (HEX.test(hex)) onChange(hex);
          }}
          onBlur={() => setTyped(null)}
          className="w-24 bg-transparent font-mono text-xs text-muted outline-none focus-visible:text-foreground"
        />
      </span>
    </label>
  );
}

export function PalettePicker({
  current,
  currentColors,
  save,
}: {
  current: Palette | null;
  currentColors: PaletteColors | null;
  save: (palette: Palette, colors?: PaletteColors) => Promise<void>;
}) {
  const t = useTranslations("appearance");
  const { setTheme } = useTheme();
  const [selected, setSelected] = useState<Palette>(current ?? "mybiz");
  const [colors, setColors] = useState<PaletteColors>(currentColors ?? DEFAULT_COLORS);
  const [dirty, setDirty] = useState(false);
  const [, start] = useTransition();
  const derived = deriveTheme(colors);
  const swatch = (palette: Palette) =>
    palette === "custom"
      ? { light: derived.tokens["--background"], ink: derived.tokens["--foreground"], accent: derived.tokens["--primary"] }
      : SWATCHES[palette];
  const adjusted = (["background", "text", "accent"] as const).filter((pick) => derived.adjusted[pick]);

  function edit(pick: (typeof PICKS)[number], hex: string) {
    const next = { ...colors, [pick]: hex };
    setColors(next);
    setDirty(true);
    apply("custom", next, setTheme);
  }

  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="mb-3 text-sm font-medium">{t("palette")}</legend>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {PALETTES.map((palette) => {
          const colorsOf = swatch(palette);
          const checked = selected === palette;
          return (
            <label
              key={palette}
              className={`group relative flex cursor-pointer flex-col gap-3 rounded-2xl border p-3 transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-primary ${
                checked ? "border-primary bg-primary/5" : "border-border hover:border-foreground/25"
              }`}
            >
              <input
                type="radio"
                name="palette"
                value={palette}
                checked={checked}
                onChange={() => {
                  setSelected(palette);
                  if (palette === "custom") {
                    // Colors are saved with the Save button, so they can be tried first.
                    apply("custom", colors, setTheme);
                    setDirty(current !== "custom");
                  } else {
                    apply(palette, null, setTheme);
                    setDirty(false);
                    start(() => save(palette));
                  }
                }}
                className="sr-only"
              />
              <span aria-hidden="true" className="flex h-14 overflow-hidden rounded-xl ring-1 ring-border">
                <span className="flex-[3]" style={{ background: colorsOf.light }} />
                <span className="flex-[2]" style={{ background: colorsOf.ink }} />
                <span className="flex-[2]" style={{ background: colorsOf.accent }} />
              </span>
              <span className="flex items-center justify-between gap-2 text-sm font-semibold">
                {t(`palettes.${palette}`)}
                {checked && <Check aria-hidden="true" className="size-4 text-primary" />}
              </span>
              <span className="text-xs text-muted">{t(`paletteHints.${palette}`)}</span>
            </label>
          );
        })}
      </div>
      {selected === "custom" && (
        <div className="flex flex-col gap-3 rounded-2xl border border-border p-4">
          <p className="text-sm text-muted">{t("customHint")}</p>
          <div className="grid gap-3 sm:grid-cols-3">
            {PICKS.map((pick) => (
              <ColorPick key={pick} label={t(`picks.${pick}`)} value={colors[pick]} onChange={(hex) => edit(pick, hex)} />
            ))}
          </div>
          {adjusted.length > 0 && (
            <p role="status" className="flex items-start gap-2 text-sm text-warning">
              <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              {t("adjusted", { picks: adjusted.map((pick) => t(`picks.${pick}`)).join(", ") })}
            </p>
          )}
          <p className="flex items-start gap-2 text-xs text-muted">
            <Lock aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
            {t("modeFollowsBackground")}
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="btn-primary px-4 py-2 text-sm"
              disabled={!dirty}
              onClick={() => {
                setDirty(false);
                start(() => save("custom", colors));
              }}
            >
              {t("saveColors")}
            </button>
            <button
              type="button"
              className="btn-secondary px-4 py-2 text-sm"
              onClick={() => {
                setColors(DEFAULT_COLORS);
                setDirty(true);
                apply("custom", DEFAULT_COLORS, setTheme);
              }}
            >
              {t("resetColors")}
            </button>
          </div>
        </div>
      )}
    </fieldset>
  );
}
