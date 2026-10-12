import type { Messages } from "./index";
import { withBrand } from "./brand";
import type { Locale } from "./locales";

/** One language's messages, read on demand so a request (and the server bundle's hot path)
 * touches a single JSON file instead of both. */
export async function loadMessages(locale: Locale): Promise<Messages> {
  const file = locale === "he" ? await import("../messages/he.json") : await import("../messages/en.json");
  return withBrand(file.default) as Messages;
}
