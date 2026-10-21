import { displayFontFamily, fontFamily } from "@business-os/design-tokens";

/**
 * Assistant family per weight (the web's three: 400 text, 500 labels, 600 headings). Use these instead of `fontWeight`: a custom font file already is one
 * weight, and mixing the two makes Android pick the wrong face. Falls back to the system font
 * until Assistant has loaded.
 */
export const font = {
  regular: { fontFamily: fontFamily.regular },
  medium: { fontFamily: fontFamily.medium },
  semibold: { fontFamily: fontFamily.semibold },
} as const;

/** The Assistant file for a CSS font weight ("bold", 600, "500"…): 600 and heavier are the semibold (800 does not exist), 500 medium, lighter regular. */
export function familyFor(weight: unknown): string {
  const w = weight === "bold" ? 700 : Number(weight ?? 400);
  if (w >= 600) return fontFamily.semibold;
  if (w >= 500) return fontFamily.medium;
  return fontFamily.regular;
}

/** Semibold English text is a heading or a number: it gets the web's display face, Plus Jakarta Sans. */
export function familyForLocale(weight: unknown, locale: string): string {
  const family = familyFor(weight);
  return locale.startsWith("en") && family === fontFamily.semibold ? displayFontFamily.semibold : family;
}

type SizedStyle = { fontSize?: number; lineHeight?: number };

/** The style with its font size and line height multiplied, so a larger text setting grows everything. */
export function scaleText<T extends SizedStyle>(style: T, scale: number): T {
  if (scale === 1) return style;
  return {
    ...style,
    // 14 is react-native's default size, used when a style names none.
    fontSize: Math.round((style.fontSize ?? 14) * scale * 10) / 10,
    ...(style.lineHeight ? { lineHeight: Math.round(style.lineHeight * scale * 10) / 10 } : {}),
  };
}
