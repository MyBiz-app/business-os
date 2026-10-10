/** Coverage rules count minutes from midnight; 1440 is the end of the day. */

/** "07:30" for 450; the end of the day (1440) reads "24:00". */
export function minuteToTime(minute: number): string {
  return `${String(Math.floor(minute / 60)).padStart(2, "0")}:${String(minute % 60).padStart(2, "0")}`;
}

/** Minutes from midnight for "HH:MM". When `end`, "00:00" means the end of the day. */
export function timeToMinute(time: string, end = false): number {
  const [h, m] = time.split(":").map(Number);
  const minute = h * 60 + m;
  return end && minute === 0 ? 1440 : minute;
}

/** Input value for a rule's end: the end of the day shows as "00:00". */
export function endInputValue(minute: number): string {
  return minuteToTime(minute === 1440 ? 0 : minute);
}
