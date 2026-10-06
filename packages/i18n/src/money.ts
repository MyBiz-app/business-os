// Money for the web and the apps. Amounts are integer minor units plus an ISO currency code
// (CLAUDE.md, principle 4); how many minor units make a major one depends on the currency
// (ILS, USD and EUR: 100; JPY: 1), so nothing here divides by 100 blindly.

const digitsCache = new Map<string, number>();

/** How many decimal places the currency uses (2 for ILS, USD and EUR; 0 for JPY). */
export function minorDigits(currency: string): number {
  let digits = digitsCache.get(currency);
  if (digits === undefined) {
    digits = new Intl.NumberFormat("en", { style: "currency", currency }).resolvedOptions().maximumFractionDigits ?? 2;
    digitsCache.set(currency, digits);
  }
  return digits;
}

/** Minor units to a major-unit number: 5990 ILS → 59.9. For charts, CSV and structured data. */
export function toMajor(amount: number, currency: string): number {
  return amount / 10 ** minorDigits(currency);
}

/** A price typed in major units ("59.90") to integer minor units (5990), or null when invalid. */
export function toMinorUnits(input: string, currency: string): number | null {
  const digits = minorDigits(currency);
  const normalized = input.trim().replace(",", ".");
  if (normalized === "") return 0;
  const pattern = digits === 0 ? /^\d+$/ : new RegExp(`^\\d+(\\.\\d{1,${digits}})?$`);
  if (!pattern.test(normalized)) return null;
  return Math.round(Number(normalized) * 10 ** digits);
}

/** Minor units back to the major-unit string shown in an input ("59.90", "60"). */
export function toMajorUnits(amount: number, currency: string): string {
  const scale = 10 ** minorDigits(currency);
  return amount % scale === 0 ? String(amount / scale) : (amount / scale).toFixed(minorDigits(currency));
}

/** Minor units as money: whole amounts without decimals ("₪120"), otherwise all of them ("₪59.90"). */
export function formatMoney(amount: number, currency: string, locale: string): string {
  const scale = 10 ** minorDigits(currency);
  const digits = amount % scale === 0 ? 0 : minorDigits(currency);
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(amount / scale);
}
