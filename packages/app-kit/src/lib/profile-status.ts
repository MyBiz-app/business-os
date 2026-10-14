/** The longest profile status the API accepts. */
export const STATUS_MAX_LENGTH = 80;

/** A status as the API stores it: trimmed, cut to the limit, empty means "no status". */
export function normalizeStatus(value: string): string | null {
  const trimmed = value.trim().slice(0, STATUS_MAX_LENGTH).trim();
  return trimmed === "" ? null : trimmed;
}

/** Whether the typed status differs from the saved one (so the save button is worth showing). */
export function statusChanged(typed: string, saved: string | null | undefined): boolean {
  return normalizeStatus(typed) !== (saved ?? null);
}
