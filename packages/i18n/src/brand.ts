// The product's name, in one place (decision X21: "MyBiz" for now). Translations write the
// name as "MyBiz"; withBrand swaps it for BRAND.name, so renaming the product is a change to
// brand.json (plus the store names in each Expo app's app.json, see docs/design-system.md).
import brand from "../brand.json";

export const BRAND: { name: string } = brand;

const WRITTEN = "MyBiz";

/** The messages with the product's name as BRAND.name (the same object while it is "MyBiz"). */
export function withBrand<T>(messages: T): T {
  if (BRAND.name === WRITTEN) return messages;
  const swap = (value: unknown): unknown => {
    if (typeof value === "string") return value.split(WRITTEN).join(BRAND.name);
    if (Array.isArray(value)) return value.map(swap);
    if (value && typeof value === "object") {
      return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, swap(item)]));
    }
    return value;
  };
  return swap(messages) as T;
}
