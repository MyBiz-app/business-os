/** Wall-clock times in a business's time zone, as instants (daylight saving included). */

function offsetMs(instant: number, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
  }).formatToParts(new Date(instant));
  const value = (type: string) => Number(parts.find((p) => p.type === type)?.value);
  const asUtc = Date.UTC(value("year"), value("month") - 1, value("day"), value("hour"), value("minute"), value("second"));
  return asUtc - Math.floor(instant / 1000) * 1000;
}

/** The instant (ISO, UTC) of a local date ("YYYY-MM-DD") and time ("HH:MM") in `timeZone`. */
export function zonedToIso(day: string, time: string, timeZone: string): string {
  const [year, month, date] = day.split("-").map(Number);
  const [hours, minutes] = time.split(":").map(Number);
  const guess = Date.UTC(year, month - 1, date, hours, minutes);
  let instant = guess - offsetMs(guess, timeZone);
  // Near a daylight-saving change the offset at the result can differ from the guess's.
  instant = guess - offsetMs(instant, timeZone);
  return new Date(instant).toISOString();
}
