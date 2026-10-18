export const TABS = ["services", "plans", "codes"] as const;
export type CatalogTab = (typeof TABS)[number];
export const SHOWS = ["all", "active", "paused"] as const;
export type CatalogShow = (typeof SHOWS)[number];

/** Gyms and studios, where a booking needs a plan, open on plans; everyone else on services. */
export function tabOrder(bookingRequiresPlan: boolean): CatalogTab[] {
  return bookingRequiresPlan ? ["plans", "services", "codes"] : ["services", "plans", "codes"];
}

export function catalogHref(tab: CatalogTab, show?: CatalogShow): string {
  const query = new URLSearchParams({ tab });
  if (show && show !== "all") query.set("show", show);
  return `/catalog?${query}`;
}
