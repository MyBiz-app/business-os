// The business's vertical as a key of the `terms` messages; older cached data has none.
const VERTICALS = ["fitness", "beauty", "clinic", "garage"] as const;
export type Vertical = (typeof VERTICALS)[number];

export function verticalOf(business: { vertical?: string | null } | null | undefined): Vertical {
  const value = business?.vertical;
  return VERTICALS.find((v) => v === value) ?? "fitness";
}
