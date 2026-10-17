/** Hours as `h:mm` (8.5 -> "8:30"), the way a time clock shows them. */
export function formatHours(hours: number): string {
  const minutes = Math.round(hours * 60);
  const sign = minutes < 0 ? "-" : "";
  const abs = Math.abs(minutes);
  return `${sign}${Math.floor(abs / 60)}:${String(abs % 60).padStart(2, "0")}`;
}

/** The length of an entry in hours; a running entry counts up to `now`. */
export function entryHours(clockIn: string, clockOut: string | null, now: Date = new Date()): number {
  const end = clockOut ? new Date(clockOut).getTime() : now.getTime();
  return Math.max(0, (end - new Date(clockIn).getTime()) / 3_600_000);
}
