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
