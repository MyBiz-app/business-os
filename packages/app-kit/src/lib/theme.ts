// Same palette as the web app's marketing site; the values live in @business-os/design-tokens.
import { highContrast, palette } from "@business-os/design-tokens";

export const colors = palette;

export type Palette = Record<keyof (typeof palette)["light"], string>;

/** The palette for a scheme, with the higher-contrast overrides when the person asked for them. */
export function paletteFor(scheme: "light" | "dark", contrast: boolean): Palette {
  return contrast ? { ...palette[scheme], ...highContrast[scheme] } : palette[scheme];
}

/** Colors that do not change with the theme or a business's brand (white on a brand fill, the
 * rating star, the warning amber for banners). Everything else comes from the palette. */
export const fixedColors = { white: "#ffffff", black: "#000000", star: "#f59e0b", amber: "#b45309" } as const;
