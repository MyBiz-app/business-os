import type { Location } from "@/lib/use-locations";

/** The app has no native map yet (it would need a native build); on a phone the branches are
 * listed with their distance and a navigate button instead. The web build draws a real map. */
export function BranchMap(_props: { locations: Location[]; selectedId?: string; onSelect?: (id: string) => void }) {
  return null;
}
