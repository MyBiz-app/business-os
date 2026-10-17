// The product's name, in one place (decision X21: "MyBiz" for now). Translations write the
// name as "MyBiz"; withBrand swaps it for BRAND.name, so renaming the product is a change to
// brand.json, then `pnpm brand:sync` for the copies the API and the Expo config need (docs/brand-rename.md).
import brand from "../brand.json";

export const BRAND: typeof brand = brand;

/** Current version of a legal document (also the date of its last change), from brand.json. */
export function legalVersion(document: keyof typeof brand.legal.versions): string {
  return brand.legal.versions[document].version;
}

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
