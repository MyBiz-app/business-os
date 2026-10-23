/**
 * Design tokens for the Expo apps. These are the web's "Calm" tokens (apps/web/src/app/globals.css,
 * docs/guides/design-system.md "Calm") as plain TypeScript: the same colors, corners, type scale and
 * spacing, so a screen looks the same on the web and in the app. `test/tokens.test.ts` compares the
 * palette with globals.css, so one cannot drift without the other. The apps' business brand color still
 * replaces `primary` per business (see app-kit `brandPalette`); `ai` is reserved for AI.
 */

export const palette = {
  light: {
    background: "#f2f2f7", // the page: the iOS grouped background
    foreground: "#1c1c1e",
    surface: "#ffffff", // cards, sheets, the tab bar
    // A quiet fill inside a surface (a track, a pressed row, a skeleton).
    subtle: "#f2f2f4",
    border: "#e6e6ea",
    muted: "#63636e", // AA on the page, the surface and every status tint
    // The one action color: Apple's web blue. iOS's #007AFF is only 4.0:1 under white button text, so
    // the light fill is this slightly deeper blue (4.7:1); dark mode uses the iOS #0A84FF.
    primary: "#0071e3",
    // Text-safe blue (links, tinted labels): 4.5:1 or more on the page, white and every tint.
    primaryInk: "#0062cc",
    onPrimary: "#ffffff",
    accent: "#06b6d4", // Electric Cyan: highlights only, never text
    ai: "#7c3aed", // AI Purple: AI features only
    // Darker than the web's #16a34a fill so it reads as text on white (WCAG AA): the web's success ink.
    success: "#137636",
    successInk: "#127a37",
    warning: "#a84a08",
    danger: "#b91c1c",
    onDanger: "#ffffff",
    // Status tints (a very light background; the matching ink is the text on it).
    successSoft: "#ecfdf3",
    warningSoft: "#fff7e6",
    dangerSoft: "#fef2f2",
    infoSoft: "#eff6ff",
    infoInk: "#0062cc",
  },
  dark: {
    background: "#000000", // iOS dark: true black page, raised grays on it
    foreground: "#f5f5f7",
    surface: "#1c1c1e",
    subtle: "#2c2c2e",
    border: "#38383a",
    muted: "#a1a1a6",
    primary: "#0a84ff",
    primaryInk: "#4da3ff",
    // Dark text on the lighter night blue: white on it is only 3.7:1.
    onPrimary: "#000000",
    accent: "#22d3ee",
    ai: "#a78bfa",
    success: "#22c55e",
    successInk: "#4ade80",
    warning: "#fbbf24",
    danger: "#f87171",
    onDanger: "#000000",
    successSoft: "#12261a",
    warningSoft: "#2a2010",
    dangerSoft: "#2a1414",
    infoSoft: "#0e2038",
    infoInk: "#4da3ff",
  },
} as const;

/** Higher-contrast overrides, applied on top of the palette when the person asks for them. */
export const highContrast = {
  light: { muted: "#334155", border: "#64748b" },
  dark: { muted: "#cbd5e1", border: "#94a3b8" },
} as const;

/**
 * Assistant covers Hebrew and Latin; the family names are the ones the font loader registers. On iPhone
 * the app uses the system font (SF) and Assistant is the fallback everywhere else, as on the web.
 * Three weights, as on the web: 400 text, 500 labels and buttons, 600 headings (800 does not exist).
 */
export const fontFamily = {
  regular: "Assistant_400Regular",
  medium: "Assistant_500Medium",
  semibold: "Assistant_600SemiBold",
} as const;

/** Plus Jakarta Sans for English headings and numbers (the web's display face); Hebrew stays in Assistant. */
export const displayFontFamily = {
  semibold: "PlusJakartaSans_600SemiBold",
} as const;

/** Text size choices (a multiplier on every font size), the same steps as the web app. */
export const textScales = { normal: 1, large: 1.125, larger: 1.25 } as const;

/**
 * Type scale: size and line height in px, Apple's text styles (11 pt caption up to the 34 pt large title).
 * Hierarchy comes from size; headline is the one 17 pt semibold.
 */
export const typeScale = {
  largeTitle: { size: 34, line: 41, weight: "semibold" },
  title1: { size: 28, line: 34, weight: "semibold" },
  title2: { size: 22, line: 28, weight: "semibold" },
  title3: { size: 20, line: 25, weight: "semibold" },
  headline: { size: 17, line: 22, weight: "semibold" },
  body: { size: 17, line: 22, weight: "regular" },
  callout: { size: 16, line: 21, weight: "regular" },
  subhead: { size: 15, line: 20, weight: "regular" },
  footnote: { size: 13, line: 18, weight: "regular" },
  caption: { size: 12, line: 16, weight: "medium" },
} as const;

/** Every font size a screen may use. */
export const fontSizes = [12, 13, 15, 16, 17, 20, 22, 28, 34] as const;

/** Spacing on a 4px grid. Cards pad `lg` (16) on a phone, sections sit `xxl` (24) apart. */
export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 20, xxl: 24, xxxl: 32 } as const;

/**
 * Corners: 10 for controls (buttons, fields), 12 for cards, 16 for windows and sheets; `xs` and `sm`
 * are for small marks (a dot, a bar, a chip); `pill` for anything fully round.
 */
export const radius = { xs: 4, sm: 8, control: 10, card: 12, dialog: 16, pill: 999 } as const;

/** Controls are 44px tall in the app (the web's touch size); the tab bar and rail rows keep 48. */
export const controlHeight = 44;

/** Smallest comfortable touch target. */
export const minTouch = 48;

/** Motion: 150 to 250 ms, eased out; nothing blocks a tap. */
export const motion = { fast: 150, base: 200, slow: 250 } as const;

/** Depth: cards are flat (a surface and a hairline); only what floats casts a shadow. */
export const elevation = {
  floating: { light: "0px 1px 3px rgba(24, 24, 27, 0.06), 0px 8px 24px rgba(24, 24, 27, 0.1)", dark: "0px 1px 3px rgba(0, 0, 0, 0.5), 0px 12px 28px rgba(0, 0, 0, 0.7)" },
} as const;
