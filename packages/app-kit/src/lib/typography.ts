import { fontFamily } from "@business-os/design-tokens";

/**
 * Heebo family per weight. Use these instead of `fontWeight`: a custom font file already is one
 * weight, and mixing the two makes Android pick the wrong face. Falls back to the system font
 * until Heebo has loaded.
 */
export const font = {
  regular: { fontFamily: fontFamily.regular },
  medium: { fontFamily: fontFamily.medium },
  bold: { fontFamily: fontFamily.bold },
} as const;

/** The Heebo file for a CSS font weight ("bold", 600, "500"…); anything lighter than 500 is regular. */
export function familyFor(weight: unknown): string {
  const w = weight === "bold" ? 700 : Number(weight ?? 400);
  if (w >= 700) return fontFamily.bold;
  if (w >= 500) return fontFamily.medium;
  return fontFamily.regular;
}
