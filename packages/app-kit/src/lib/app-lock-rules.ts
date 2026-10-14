/** The app locks again after being in the background for this long. */
export const LOCK_AFTER_MS = 30_000;

/** Whether the app must be locked on coming back to the foreground. */
export function shouldLock(enabled: boolean, backgroundedAt: number | null, now: number): boolean {
  return enabled && backgroundedAt !== null && now - backgroundedAt >= LOCK_AFTER_MS;
}
