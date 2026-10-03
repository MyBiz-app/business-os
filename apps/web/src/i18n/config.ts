export const locales = ["he", "en"] as const;
export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = "he";

export const localeDirection: Record<Locale, "rtl" | "ltr"> = {
  he: "rtl",
  en: "ltr",
};

export const LOCALE_COOKIE = "NEXT_LOCALE";

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (locales as readonly string[]).includes(value);
}

/** Picks the first supported locale from an Accept-Language header. */
export function matchAcceptLanguage(header: string | null): Locale | undefined {
  if (!header) return undefined;
  for (const part of header.split(",")) {
    const tag = part.split(";")[0]?.trim().toLowerCase();
    const base = tag?.split("-")[0];
    if (base === "iw") return "he";
    if (isLocale(base)) return base;
  }
  return undefined;
}
