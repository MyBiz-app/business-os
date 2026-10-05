// Same design tokens as the web app (apps/web/src/app/globals.css).
export const colors = {
  light: {
    background: "#f6f6f9",
    foreground: "#18181b",
    surface: "#ffffff",
    border: "#e4e4ea",
    muted: "#52525b",
    primary: "#4f46e5",
    onPrimary: "#ffffff",
    success: "#15803d",
    danger: "#b91c1c",
  },
  dark: {
    background: "#0a0a0f",
    foreground: "#fafafa",
    surface: "#15151c",
    border: "#2a2a33",
    muted: "#a1a1aa",
    primary: "#818cf8",
    onPrimary: "#09090b",
    success: "#22c55e",
    danger: "#f87171",
  },
} as const;

export type Palette = Record<keyof (typeof colors)["light"], string>;
