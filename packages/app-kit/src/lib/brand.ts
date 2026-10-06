import type { Palette } from "./theme";

// Same contrast rule as the web app (apps/web/src/lib/brand.ts).
function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrastRatio(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

/** White or near-black, whichever reads better on the brand color. */
export function textOn(hex: string): string {
  return contrastRatio(hex, "#ffffff") >= contrastRatio(hex, "#18181b") ? "#ffffff" : "#18181b";
}

function mix(from: string, to: string, t: number): string {
  const channel = (hex: string, i: number) => parseInt(hex.slice(i, i + 2), 16);
  return `#${[1, 3, 5]
    .map((i) => Math.round(channel(from, i) + (channel(to, i) - channel(from, i)) * t))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("")}`;
}

/** Darkens (light theme) or lightens (dark theme) the brand color just enough to be readable
 * as text on the surface, and for text on it to be readable too (WCAG AA), as on the web.
 * A mid-tone (a purple, say) can pass the first and still fail the second. */
function readableOn(hex: string, surface: string): string {
  const toward = luminance(surface) > 0.5 ? "#000000" : "#ffffff";
  for (let t = 0; t <= 1; t += 0.05) {
    const color = mix(hex, toward, t);
    if (contrastRatio(color, surface) >= 4.5 && contrastRatio(color, textOn(color)) >= 4.5) return color;
  }
  return toward;
}

/** The palette with the business's brand color as primary. */
export function brandPalette(palette: Palette, color: string | null | undefined): Palette {
  if (!color) return palette;
  const primary = readableOn(color, palette.surface);
  return { ...palette, primary, onPrimary: textOn(primary) };
}

/** The color at the given opacity, for soft tints (`#rrggbb` only; anything else is returned as is). */
export function tint(hex: string, alpha: number): string {
  if (!/^#[0-9a-f]{6}$/i.test(hex)) return hex;
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
