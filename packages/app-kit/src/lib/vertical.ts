import { knownCards, type HomeCard } from "./client-home";
import { useLocale, useTranslations } from "use-intl";
import { isVertical, termOf, textKey, vertical, type TermKey, type TermsSource } from "@business-os/verticals";

/** A business's word (clients, schedule, …): its owner's own where they renamed one, else the
 * industry's. Every screen words a business through this. */
export function useTerm(): (business: TermsSource | null | undefined, name: TermKey) => string {
  const tTerms = useTranslations("terms") as unknown as (path: string) => string;
  const locale = useLocale();
  return (business, name) => termOf(business, locale, name, tTerms);
}

/** The translator's `t` and `t.has`, loosely typed for dynamic industry keys. */
type Translator = { (key: never): string; has(key: never): boolean };

/** An industry's display name ("כושר ואימון"), from it or its nearest parent; unknown keys as is. */
export function industryName(t: Translator, key: string | null | undefined): string {
  if (!key || !isVertical(key)) return key ?? "";
  const lookup = t as unknown as { (key: string): string; has(key: string): boolean };
  return lookup(textKey(key, "name", (path) => lookup.has(path)));
}

/** Whether a business's industry keeps its clients' pets or children (#43), and whether every
 * booking must say which one comes. */
export function dependentsFor(business: { vertical?: string | null } | null | undefined): {
  kind: "pet" | "child" | null;
  required: boolean;
} {
  const entry = business?.vertical && isVertical(business.vertical) ? vertical(business.vertical) : undefined;
  return { kind: entry?.dependents ?? null, required: entry?.dependentRequired ?? false };
}

/** Whether a business's industry bills by time (#45): time entries on the client card. */
export function billsByTime(business: { vertical?: string | null } | null | undefined): boolean {
  const entry = business?.vertical && isVertical(business.vertical) ? vertical(business.vertical) : undefined;
  return entry?.timeBilling ?? false;
}

/** The cards of the client's home, top to bottom: the API's list for the business, or the
 * industry catalog's when the API predates it. */
export function homeCardsFor(business: { vertical?: string | null; home_cards?: string[] | null } | null | undefined): HomeCard[] {
  const listed = business?.home_cards?.length ? business.home_cards : vertical(business?.vertical)?.clientHome;
  return knownCards(listed ?? ["next_booking", "shortcuts", "updates", "business_info"]);
}

/** The kinds of booking an industry takes: classes, appointments, rentals by the hour. */
export function bookingModesFor(business: { vertical?: string | null } | null | undefined): string[] {
  return vertical(business?.vertical)?.bookingModes ?? [];
}

/** How clients see the schedule: class blocks, appointments by staff member, or courts by the hour. */
export function scheduleViewFor(business: { vertical?: string | null } | null | undefined): "class_blocks" | "appointments" | "courts" {
  return vertical(business?.vertical)?.scheduleView ?? "class_blocks";
}
