/**
 * The business's own words. An industry brings default words (`terms.<set>` in the translations);
 * an owner may rename some of them ("clients" to "club members"), per language. Every screen
 * reads a word through `termOf` so the rename shows everywhere at once.
 */
import { termsOf } from "./index";

/** The words an owner may rename; the API keeps the same list (a test keeps both equal to the
 * translated words). Words with a count in them are not renameable. */
export const TERM_KEYS = [
  "client", "clients", "addClient", "newClient", "searchClients", "noClients", "noResults",
  "schedule", "newSession", "noSessions", "appTab", "appEmpty", "place", "profile", "visitNotes",
  "nextBooking",
] as const;
export type TermKey = (typeof TERM_KEYS)[number];

/** Language, then word, then the owner's text. */
export type TermsOverride = Record<string, Record<string, string>>;

/** What a screen needs to know about a business to word things for it. */
export type TermsSource = { vertical?: string | null; terms_override?: TermsOverride | null };

/** The owner's text for a word in a language, if they set one. */
export function termOverride(business: TermsSource | null | undefined, locale: string, name: string): string | undefined {
  const text = business?.terms_override?.[locale]?.[name];
  return text && text.trim() ? text : undefined;
}

/** A word for a business: the owner's own, else the industry's through `lookup`, the translator
 * for `terms.<set>.<name>`. */
export function termOf(
  business: TermsSource | null | undefined,
  locale: string,
  name: string,
  lookup: (path: string) => string,
): string {
  return termOverride(business, locale, name) ?? lookup(`${termsOf(business?.vertical)}.${name}`);
}
