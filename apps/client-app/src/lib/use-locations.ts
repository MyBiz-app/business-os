import type { components } from "@business-os/api-client";
import { useCachedLoad } from "@business-os/app-kit/lib/use-cached-load";
import { dataKey, fetchLocations } from "@/lib/client-data";
import { useDataContext } from "@/lib/use-data-context";

export type Location = components["schemas"]["ClientLocation"];

const NONE: Location[] = [];

/** The business's branches with their addresses (empty until loaded or when none is set). */
export function useLocations(): Location[] {
  const ctx = useDataContext();
  const { data } = useCachedLoad(
    ctx ? dataKey(ctx, "locations-list") : ["locations-list"],
    () => (ctx ? fetchLocations(ctx) : Promise.resolve(NONE)),
    { enabled: Boolean(ctx) },
  );
  return ctx ? (data ?? NONE) : NONE;
}

/** The address to navigate to for a booking at the named branch; a business with a single
 * branch needs no name. */
export function addressOf(locations: Location[], branchName?: string | null): string | null {
  const branch = locations.find((l) => l.name === branchName) ?? (locations.length === 1 ? locations[0] : undefined);
  return branch?.address ?? null;
}
