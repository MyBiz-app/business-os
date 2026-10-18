import type { components } from "@business-os/api-client";

import { API_URL } from "@/lib/api";

export type Catalog = components["schemas"]["Catalog"];

/** The public price catalog in one currency, or null while the API is unreachable. */
export async function loadCatalog(currency: string): Promise<Catalog | null> {
  try {
    const response = await fetch(`${API_URL}/public/pricing?currency=${currency}`, { next: { revalidate: 3600 } });
    return response.ok ? ((await response.json()) as Catalog) : null;
  } catch {
    return null;
  }
}

export type SitePrices = components["schemas"]["WebsitePrices"];

/** The website price list in one currency (the API's single list), or null while it is unreachable. */
export async function loadSitePrices(currency: string): Promise<SitePrices | null> {
  try {
    const response = await fetch(`${API_URL}/public/website-prices?currency=${currency}`, { next: { revalidate: 3600 } });
    return response.ok ? ((await response.json()) as SitePrices) : null;
  } catch {
    return null;
  }
}
