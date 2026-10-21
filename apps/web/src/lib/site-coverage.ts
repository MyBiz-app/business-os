import type { components } from "@business-os/api-client";

import { API_URL } from "@/lib/api";

export type Coverage = components["schemas"]["Coverage"];

/** The cities that have at least five MyBiz businesses (counts only, no names), or null while the
 * API is unreachable. The page hides its map when there is nothing to show. */
export async function loadCoverage(): Promise<Coverage | null> {
  try {
    const response = await fetch(`${API_URL}/public/geo/coverage`, { next: { revalidate: 3600 } });
    return response.ok ? ((await response.json()) as Coverage) : null;
  } catch {
    return null;
  }
}
