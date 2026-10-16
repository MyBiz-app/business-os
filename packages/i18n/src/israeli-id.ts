/** Israeli ID numbers (ת.ז.): up to 9 digits with a check digit. The API checks the same rule. */

/** Only the digits of what the person typed ("12-345 6782" becomes "123456782"). */
export function idDigits(value: string): string {
  return value.replace(/\D/g, "");
}

/** True when `value` is a real Israeli ID: at most 9 digits, zero-padded, weights 1,2,1,2... */
export function israeliIdValid(value: string): boolean {
  const digits = idDigits(value);
  if (!/^\d{1,9}$/.test(value.replace(/[\s-]/g, "")) || Number(digits) === 0) return false;
  let total = 0;
  digits
    .padStart(9, "0")
    .split("")
    .forEach((digit, index) => {
      const product = Number(digit) * (1 + (index % 2));
      total += product > 9 ? product - 9 : product;
    });
  return total % 10 === 0;
}

/** What screens show instead of the number. */
export function maskedId(last4: string): string {
  return `•••••${last4}`;
}
