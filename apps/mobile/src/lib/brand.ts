import type { Palette } from "@/lib/theme";

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

/** The palette with the business's brand color as primary. */
export function brandPalette(palette: Palette, color: string | null | undefined): Palette {
  if (!color) return palette;
  return { ...palette, primary: color, onPrimary: textOn(color) };
}
