/** "My own colors" (docs/proposals/profile-crop-and-palette.md): the person picks a background,
 * a text color and an accent; every color the app needs is derived from them and pushed to a
 * readable contrast, so no choice can make a part of the screen unreadable or invisible.
 * Pure functions, no DOM, so they are tested. */

export type PaletteColors = { background: string; text: string; accent: string };

export const DEFAULT_COLORS: PaletteColors = { background: "#ffffff", text: "#0a0a0a", accent: "#6d28d9" };

export const HEX = /^#[0-9a-f]{6}$/;

type Rgb = [number, number, number];

export function parseHex(value: string, fallback: string): string {
  const hex = value.trim().toLowerCase();
  return HEX.test(hex) ? hex : fallback;
}

function toRgb(hex: string): Rgb {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)) as Rgb;
}

function toHex(rgb: Rgb): string {
  return `#${rgb.map((v) => Math.round(Math.min(255, Math.max(0, v))).toString(16).padStart(2, "0")).join("")}`;
}

export function luminance(hex: string): number {
  const [r, g, b] = toRgb(hex).map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** `amount` (0..1) of `towards` mixed into `color`. */
export function mix(color: string, towards: string, amount: number): string {
  const a = toRgb(color);
  const b = toRgb(towards);
  return toHex(a.map((v, i) => v + (b[i] - v) * amount) as Rgb);
}

/** The color closest to `color` (same hue, moved toward white or black) that reads at least
 * `min`:1 against every background in `against`. */
export function readable(color: string, against: string[], min: number): string {
  const ok = (c: string) => against.every((bg) => contrast(c, bg) >= min);
  if (ok(color)) return color;
  // Away from the backgrounds: toward white on dark ones, black on light ones.
  const average = against.reduce((sum, bg) => sum + luminance(bg), 0) / against.length;
  const targets = average < 0.4 ? ["#ffffff", "#000000"] : ["#000000", "#ffffff"];
  for (const target of targets) {
    for (let step = 1; step <= 50; step++) {
      const candidate = mix(color, target, step / 50);
      if (ok(candidate)) return candidate;
    }
  }
  return targets[0];
}

/** A middle-gray page cannot carry text at 7:1 in either black or white, so such a background
 * is moved (toward black or white, whichever is nearer) until one of them can. */
function usable(background: string): string {
  const lum = luminance(background);
  if (lum <= 0.07 || lum >= 0.4) return background;
  const target = lum < 0.2 ? "#000000" : "#ffffff";
  for (let step = 1; step <= 100; step++) {
    const candidate = mix(background, target, step / 100);
    const l = luminance(candidate);
    if (l <= 0.07 || l >= 0.4) return candidate;
  }
  return target;
}

export type DerivedTheme = {
  scheme: "light" | "dark";
  /** CSS custom properties to set on <html>. */
  tokens: Record<string, string>;
  /** Which picks had to change to stay readable. */
  adjusted: { background: boolean; text: boolean; accent: boolean };
};

export function deriveTheme(input: PaletteColors): DerivedTheme {
  const picked = parseHex(input.background, DEFAULT_COLORS.background);
  const background = usable(picked);
  const scheme = luminance(background) < 0.2 ? "dark" : "light";
  const firstText = readable(parseHex(input.text, DEFAULT_COLORS.text), [background], 7);
  const surface = mix(background, firstText, 0.05);
  const text = readable(firstText, [background, surface], 7);
  const accent = readable(parseHex(input.accent, DEFAULT_COLORS.accent), [background, surface], 4.5);
  const onAccent = contrast(accent, "#ffffff") >= contrast(accent, "#0a0a0a") ? "#ffffff" : "#0a0a0a";
  const status = (light: string, dark: string) => readable(scheme === "dark" ? dark : light, [background, surface], 4.5);
  const eq = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();
  return {
    scheme,
    tokens: {
      "--background": background,
      "--foreground": text,
      "--surface": surface,
      "--border": mix(background, text, 0.16),
      "--muted": readable(mix(text, background, 0.4), [background, surface], 4.5),
      "--palette-primary": accent,
      "--palette-on-primary": onAccent,
      "--primary": accent,
      "--on-primary": onAccent,
      "--success": status("#15803d", "#22c55e"),
      "--danger": status("#b91c1c", "#f87171"),
      "--warning": status("#b45309", "#fbbf24"),
    },
    adjusted: {
      background: background !== picked,
      text: !eq(text, parseHex(input.text, DEFAULT_COLORS.text)),
      accent: !eq(accent, parseHex(input.accent, DEFAULT_COLORS.accent)),
    },
  };
}
