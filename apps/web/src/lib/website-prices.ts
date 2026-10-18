// The "MyBiz Sites" price list shown on /websites. One place to change a price; amounts are
// integer minor units per ISO currency (CLAUDE.md, principle 4). Monthly = hosting and upkeep.

export type SitePrice = { setup: number; monthly: number };

export type SiteCurrency = "ILS" | "USD" | "EUR";

/** A website on its own, and the same website for a business that also runs on MyBiz. */
export const SITE_PRICES: Record<SiteCurrency, { alone: SitePrice; withSystem: SitePrice }> = {
  ILS: { alone: { setup: 79000, monthly: 4900 }, withSystem: { setup: 49000, monthly: 2900 } },
  USD: { alone: { setup: 22900, monthly: 1400 }, withSystem: { setup: 14900, monthly: 900 } },
  EUR: { alone: { setup: 21900, monthly: 1300 }, withSystem: { setup: 13900, monthly: 800 } },
};

export function sitePricesFor(currency: string) {
  return SITE_PRICES[(currency in SITE_PRICES ? currency : "USD") as SiteCurrency];
}
