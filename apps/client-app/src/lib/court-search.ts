/** Pure helpers for the "When suits you?" court search. */

export const PREFERRED_LENGTHS = [60, 90, 120] as const;

type Lengths = { min_minutes: number; max_minutes: number; step_minutes: number };

/** The lengths a client picks from: 1h / 1.5h / 2h when the court offers them, else everything it offers. */
export function rentalLengths(service: Lengths): number[] {
  const offered = (minutes: number) =>
    minutes >= service.min_minutes && minutes <= service.max_minutes && (minutes - service.min_minutes) % service.step_minutes === 0;
  const preferred = PREFERRED_LENGTHS.filter(offered);
  if (preferred.length > 0) return [...preferred];
  const count = Math.floor((service.max_minutes - service.min_minutes) / service.step_minutes) + 1;
  return Array.from({ length: count }, (_, i) => service.min_minutes + i * service.step_minutes);
}

/** Start times to ask for, as local "HH:MM" every half hour. */
export function timeOptions(fromHour = 6, toHour = 23): string[] {
  const out: string[] = [];
  for (let h = fromHour; h <= toHour; h++) {
    out.push(`${String(h).padStart(2, "0")}:00`);
    if (h < toHour) out.push(`${String(h).padStart(2, "0")}:30`);
  }
  return out;
}

/** The next full hour in the business's time zone, kept inside the offered range. */
export function defaultTime(timeZone: string, now: Date = new Date(), options = timeOptions()): string {
  const hour = Number(
    new Intl.DateTimeFormat("en-GB", { timeZone, hour: "2-digit", hourCycle: "h23" }).format(now),
  );
  const wanted = `${String(Math.min(hour + 1, 23)).padStart(2, "0")}:00`;
  if (options.includes(wanted)) return wanted;
  return wanted < options[0]! ? options[0]! : options[options.length - 1]!;
}

/** A distance in minutes split for display: 90 → { hours: 1, minutes: 30 }. */
export function splitOffset(offsetMinutes: number): { later: boolean; hours: number; minutes: number } {
  const abs = Math.abs(offsetMinutes);
  return { later: offsetMinutes > 0, hours: Math.floor(abs / 60), minutes: abs % 60 };
}

/** Groups free slots by court, keeping the order of first appearance. */
export function groupByCourt<T extends { room_id: string; room_name: string }>(slots: T[]): { roomId: string; name: string; slots: T[] }[] {
  const groups = new Map<string, { roomId: string; name: string; slots: T[] }>();
  for (const slot of slots) {
    const group = groups.get(slot.room_id) ?? { roomId: slot.room_id, name: slot.room_name, slots: [] };
    group.slots.push(slot);
    groups.set(slot.room_id, group);
  }
  return [...groups.values()];
}
