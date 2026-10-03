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
// The surfaces the brand color sits on (globals.css --surface, light and dark).
const LIGHT_SURFACE = "#f4f4f5";
const DARK_SURFACE = "#18181b";
const AA = 4.5;

/** Text color for content placed on a brand color: whichever of white/near-black reads better. */
export function textOn(hex: string): string {
  return contrastRatio(hex, WHITE) >= contrastRatio(hex, NEAR_BLACK) ? WHITE : NEAR_BLACK;
}

/** Mixes two #rrggbb colors; t = 0 is `from`, t = 1 is `to`. */
export function mix(from: string, to: string, t: number): string {
  const channel = (hex: string, i: number) => parseInt(hex.slice(i, i + 2), 16);
  return `#${[1, 3, 5]
    .map((i) => Math.round(channel(from, i) + (channel(to, i) - channel(from, i)) * t))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("")}`;
}

/** The brand color, darkened (light theme) or lightened (dark theme) just enough to be readable
 * as text on the surface and on a 10% tint of itself (WCAG AA). */
export function readableOn(hex: string, surface: string): string {
  const toward = luminance(surface) > 0.5 ? "#000000" : WHITE;
  for (let t = 0; t <= 1; t += 0.05) {
    const color = mix(hex, toward, t);
    const tint = mix(surface, color, 0.1);
    if (contrastRatio(color, surface) >= AA && contrastRatio(color, tint) >= AA) return color;
  }
  return toward;
}

/** CSS variables for a business's brand color, read by the `.brand` class (globals.css), which
 * picks the light or dark variant. */
export function brandStyle(primary: string | null | undefined): React.CSSProperties | undefined {
  if (!primary) return undefined;
  const light = readableOn(primary, LIGHT_SURFACE);
  const dark = readableOn(primary, DARK_SURFACE);
  return {
    "--brand": light,
    "--on-brand": textOn(light),
    "--brand-dark": dark,
    "--on-brand-dark": textOn(dark),
  } as React.CSSProperties;
}
