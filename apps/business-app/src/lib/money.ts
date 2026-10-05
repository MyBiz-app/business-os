/** Minor units as money, whole amounts without decimals (same rule as the web). */
export function formatMoney(amount: number, currency: string, locale: string): string {
  const digits = amount % 100 === 0 ? 0 : 2;
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(amount / 100);
}
