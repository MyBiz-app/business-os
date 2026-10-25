// Same palette as the web app's marketing site; the values live in @business-os/design-tokens.
import { highContrast, palette } from "@business-os/design-tokens";

export const colors = palette;

export type Palette = Record<keyof (typeof palette)["light"], string>;

/** The palette for a scheme, with the higher-contrast overrides when the person asked for them. */
export function paletteFor(scheme: "light" | "dark", contrast: boolean): Palette {
  return contrast ? { ...palette[scheme], ...highContrast[scheme] } : palette[scheme];
}

/** The dim layer behind a modal or sheet. Darker in the dark theme, where a 50% black veil barely
 * separates a dark dialog from a dark page. */
export function scrimColor(scheme: "light" | "dark"): string {
  return `rgba(0, 0, 0, ${scheme === "dark" ? 0.72 : 0.5})`;
}

/** Colors that do not change with the theme or a business's brand (white on a brand fill, the
 * rating star, the warning amber for banners). Everything else comes from the palette. */
export const fixedColors = { white: "#ffffff", black: "#000000", star: "#f59e0b", amber: "#b45309", toast: "#1c2230", toastInk: "#f4f6fa", toastMuted: "#a9b1c2" } as const;

/** The shared scales, re-exported so a screen imports its colors, corners and spacing from one place. */
export { controlHeight, motion, radius, space } from "@business-os/design-tokens";
