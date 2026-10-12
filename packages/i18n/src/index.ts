import en from "../messages/en.json";
import he from "../messages/he.json";
import { withBrand } from "./brand";
import type { Locale } from "./locales";

export * from "./locales";

export type Messages = typeof en;

// Both languages at once, for the Expo apps. The web app loads one language per request with
// `loadMessages` (./load) and never imports this file.
// The product's name comes from brand.json (decision X21).
export const messages: Record<Locale, Messages> = { he: withBrand(he), en: withBrand(en) };
