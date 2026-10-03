/** Relative luminance of a #rrggbb color (WCAG 2.x). */
function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrastRatio(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

const WHITE = "#ffffff";
const NEAR_BLACK = "#18181b";

/** Text color for content placed on a brand color: whichever of white/near-black reads better. */
export function textOn(hex: string): string {
  return contrastRatio(hex, WHITE) >= contrastRatio(hex, NEAR_BLACK) ? WHITE : NEAR_BLACK;
}

/** CSS variables that apply a business's brand color to its area of the app. */
export function brandStyle(primary: string | null | undefined): React.CSSProperties | undefined {
  if (!primary) return undefined;
  return { "--primary": primary, "--on-primary": textOn(primary) } as React.CSSProperties;
}
