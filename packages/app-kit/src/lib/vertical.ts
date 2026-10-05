import { termsOf } from "@business-os/verticals";

/** The set of industry words (`terms.<set>` in the translations) for a business, from the
 * industry catalog; a sub-category uses its category's words, older cached data the default. */
export function termsFor(business: { vertical?: string | null } | null | undefined): string {
  return termsOf(business?.vertical);
}
