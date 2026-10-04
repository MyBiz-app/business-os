/** Converts a price typed in major units ("59.90") to integer minor units (5990). */
export function toMinorUnits(input: string): number | null {
  const normalized = input.trim().replace(",", ".");
  if (normalized === "") return 0;
  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) return null;
  return Math.round(Number(normalized) * 100);
}

/** Minor units back to the major-unit string shown in an input ("59.90", "60"). */
export function toMajorUnits(amount: number): string {
  return amount % 100 === 0 ? String(amount / 100) : (amount / 100).toFixed(2);
}

export function formatMoney(amount: number, currency: string, locale: string): string {
  // Whole amounts without decimals ("₪120"), otherwise always two ("₪59.90").
  const fractionDigits = amount % 100 === 0 ? 0 : 2;
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(amount / 100);
}
