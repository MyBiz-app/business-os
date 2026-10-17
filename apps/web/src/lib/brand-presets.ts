/** The ready-made brand colors offered in Settings → Branding, in display order. The first is the
 * default. Labels are `settings.branding.presets.<key>` in the translations. */
export const BRAND_PRESETS = [
  { key: "blue", color: "#2563eb" },
  { key: "purple", color: "#7c3aed" },
  { key: "teal", color: "#0d9488" },
  { key: "green", color: "#16a34a" },
  { key: "orange", color: "#ea580c" },
  { key: "red", color: "#dc2626" },
  { key: "pink", color: "#db2777" },
  { key: "slate", color: "#334155" },
] as const;
