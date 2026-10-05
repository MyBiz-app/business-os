import { todayIn } from "@/lib/dates";

/** A month as "YYYY-MM" (this month in the business's time zone when missing or invalid),
 * with its first and last day. */
export function monthRange(value: unknown, timeZone: string) {
  const month = typeof value === "string" && /^\d{4}-(0[1-9]|1[0-2])$/.test(value) ? value : todayIn(timeZone).slice(0, 7);
  const [year, number] = month.split("-").map(Number);
  const last = new Date(Date.UTC(year, number, 0)).getUTCDate();
  const shift = (delta: number) => {
    const d = new Date(Date.UTC(year, number - 1 + delta, 1));
    return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
  };
  return { month, start: `${month}-01`, end: `${month}-${String(last).padStart(2, "0")}`, previous: shift(-1), next: shift(1) };
}
