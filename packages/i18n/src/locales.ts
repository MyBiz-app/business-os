// Locale list and helpers only: no message files, so client bundles can import it cheaply.
export const locales = ["he", "en"] as const;
export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = "he";

export const localeDirection: Record<Locale, "rtl" | "ltr"> = {
  he: "rtl",
  en: "ltr",
};

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (locales as readonly string[]).includes(value);
}

/** Maps a language tag ("he-IL", "iw", "en-US") to a supported locale. */
export function matchLanguageTag(tag: string | null | undefined): Locale | undefined {
  const base = tag?.trim().toLowerCase().split(/[-_]/)[0];
  if (base === "iw") return "he";
  return isLocale(base) ? base : undefined;
}

/** Picks the first supported locale from an Accept-Language header. */
export function matchAcceptLanguage(header: string | null): Locale | undefined {
  if (!header) return undefined;
  for (const part of header.split(",")) {
    const locale = matchLanguageTag(part.split(";")[0]);
    if (locale) return locale;
  }
  return undefined;
}
