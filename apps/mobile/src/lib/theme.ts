// Same design tokens as the web app (apps/web/src/app/globals.css).
export const colors = {
  light: {
    background: "#ffffff",
    foreground: "#18181b",
    surface: "#f4f4f5",
    border: "#e4e4e7",
    muted: "#52525b",
    primary: "#4f46e5",
    onPrimary: "#ffffff",
    success: "#15803d",
    danger: "#b91c1c",
  },
  dark: {
    background: "#09090b",
    foreground: "#fafafa",
    surface: "#18181b",
    border: "#27272a",
    muted: "#a1a1aa",
    primary: "#818cf8",
    onPrimary: "#09090b",
    success: "#22c55e",
    danger: "#f87171",
  },
} as const;

export type Palette = Record<keyof (typeof colors)["light"], string>;
