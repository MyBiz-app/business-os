/**
 * Design tokens for the Expo apps: the same MyBiz palette as the web marketing site
 * (`.mk` in apps/web/src/app/globals.css), as plain TypeScript. The apps' business brand color
 * still replaces `primary` per business (see app-kit `brandPalette`); `ai` is reserved for AI.
 */
export const palette = {
  light: {
    background: "#f8fafc", // Cloud White
    foreground: "#111827", // Midnight Navy
    surface: "#ffffff", // Pure White
    border: "#e2e8f0",
    muted: "#64748b", // Slate Gray
    primary: "#2563eb", // Primary Blue
    onPrimary: "#ffffff",
    accent: "#06b6d4", // Electric Cyan: highlights only, never text
    ai: "#7c3aed", // AI Purple: AI features only
    // Darker than the brand's #16a34a so it reads as text on white (WCAG AA).
    success: "#15803d",
    warning: "#b45309",
    danger: "#b91c1c",
  },
  dark: {
    background: "#0b1020",
    foreground: "#f8fafc",
    surface: "#111827",
    border: "#263247",
    muted: "#94a3b8",
    primary: "#3b82f6",
    onPrimary: "#0b1020",
    accent: "#22d3ee",
    ai: "#a78bfa",
    success: "#22c55e",
    warning: "#fbbf24",
    danger: "#f87171",
  },
} as const;

/** Higher-contrast overrides, applied on top of the palette when the person asks for them. */
export const highContrast = {
  light: { muted: "#334155", border: "#64748b" },
  dark: { muted: "#cbd5e1", border: "#94a3b8" },
} as const;

/** Heebo covers Hebrew and Latin; the family names are the ones the font loader registers. */
export const fontFamily = {
  regular: "Heebo_400Regular",
  medium: "Heebo_500Medium",
  bold: "Heebo_700Bold",
} as const;

/** Type scale: size and line height in px. */
export const typeScale = {
  display: { size: 28, line: 34, weight: "bold" },
  title: { size: 20, line: 26, weight: "bold" },
  body: { size: 16, line: 24, weight: "regular" },
  secondary: { size: 14, line: 20, weight: "regular" },
  label: { size: 12, line: 16, weight: "medium" },
} as const;

/** Spacing on an 8px base (4 for tight gaps). */
export const space = { xs: 4, sm: 8, md: 16, lg: 24, xl: 32 } as const;

export const radius = { field: 14, card: 20, sheet: 28, pill: 999 } as const;

/** Smallest comfortable touch target. */
export const minTouch = 48;
