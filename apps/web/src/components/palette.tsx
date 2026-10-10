"use client";

import { Check } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState, useTransition } from "react";

export const PALETTES = ["mybiz", "ocean", "forest"] as const;
export type Palette = (typeof PALETTES)[number];
export const PALETTE_KEY = "palette";

function apply(palette: Palette) {
  const root = document.documentElement;
  if (palette === "mybiz") delete root.dataset.palette;
  else root.dataset.palette = palette;
  try {
    localStorage.setItem(PALETTE_KEY, palette);
  } catch {
    // private browsing: the account still keeps it
  }
}

/** Follows the palette saved on the account (another device may have changed it). */
export function PaletteSync({ palette }: { palette: Palette | null }) {
  useEffect(() => {
    if (palette) apply(palette);
  }, [palette]);
  return null;
}

// The swatches show each palette's own colors, whatever the current one is.
const SWATCHES: Record<Palette, { light: string; ink: string; accent: string }> = {
  mybiz: { light: "#ffffff", ink: "#0a0a0a", accent: "#6d28d9" },
  ocean: { light: "#f4f7f9", ink: "#0b1a22", accent: "#0e7490" },
  forest: { light: "#f5f7f4", ink: "#0f1611", accent: "#166534" },
};

export function PalettePicker({ current, save }: { current: Palette | null; save: (palette: Palette) => Promise<void> }) {
  const t = useTranslations("appearance");
  const [selected, setSelected] = useState<Palette>(current ?? "mybiz");
  const [, start] = useTransition();
  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="mb-3 text-sm font-medium">{t("palette")}</legend>
      <div className="grid gap-3 sm:grid-cols-3">
        {PALETTES.map((palette) => {
          const swatch = SWATCHES[palette];
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
                  apply(palette);
                  start(() => save(palette));
                }}
                className="sr-only"
              />
              <span aria-hidden="true" className="flex h-14 overflow-hidden rounded-xl ring-1 ring-border">
                <span className="flex-[3]" style={{ background: swatch.light }} />
                <span className="flex-[2]" style={{ background: swatch.ink }} />
                <span className="flex-[2]" style={{ background: swatch.accent }} />
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
    </fieldset>
  );
}
