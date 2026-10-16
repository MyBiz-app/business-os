/** Pure helpers for the schedule's availability views: courts × hours and appointments by staff member. */

type Timed = { starts_at: string };

/** Local "HH:MM" of an instant in a time zone. */
export function clockOf(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-GB", { timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(iso));
}

export type CourtGrid<T> = { hours: string[]; courts: { roomId: string; name: string; cells: Record<string, T> }[] };

/** Free court slots as a table: one column per start time, one row per court (first appearance order). */
export function courtGrid<T extends Timed & { room_id: string; room_name: string }>(slots: T[], timeZone: string): CourtGrid<T> {
  const hours = [...new Set(slots.map((s) => clockOf(s.starts_at, timeZone)))].sort();
  const courts = new Map<string, { roomId: string; name: string; cells: Record<string, T> }>();
  for (const slot of slots) {
    const row = courts.get(slot.room_id) ?? { roomId: slot.room_id, name: slot.room_name, cells: {} };
    row.cells[clockOf(slot.starts_at, timeZone)] = slot;
    courts.set(slot.room_id, row);
  }
  return { hours, courts: [...courts.values()] };
}

/** Free appointment slots grouped by the staff member who takes them, each person's times in order. */
export function staffRows<T extends Timed & { staff_user_id: string; staff_name: string }>(
  slots: T[],
): { staffId: string; name: string; slots: T[] }[] {
  const rows = new Map<string, { staffId: string; name: string; slots: T[] }>();
  for (const slot of slots) {
    const row = rows.get(slot.staff_user_id) ?? { staffId: slot.staff_user_id, name: slot.staff_name, slots: [] };
    row.slots.push(slot);
    rows.set(slot.staff_user_id, row);
  }
  for (const row of rows.values()) row.slots.sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  return [...rows.values()].sort((a, b) => a.name.localeCompare(b.name));
}
