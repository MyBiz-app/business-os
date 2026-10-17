/** The app signs people out after this long without being opened (the web app uses 12 hours). */
export const SESSION_MAX_IDLE_MS = 30 * 24 * 60 * 60 * 1000;
/** The last-opened stamp is refreshed at most this often. */
export const ACTIVITY_REFRESH_MS = 60 * 60 * 1000;

/** Whether the app has not been opened for too long. No stamp (first launch) counts as active. */
export function isSessionStale(lastActive: number | null, now: number, limit = SESSION_MAX_IDLE_MS): boolean {
  return lastActive !== null && now - lastActive > limit;
}

/** Whether the stamp should be written again. */
export function shouldRefreshStamp(lastActive: number | null, now: number): boolean {
  return lastActive === null || now - lastActive > ACTIVITY_REFRESH_MS;
}

/** The person has an authenticator but has not entered a code in this session yet. */
export function needsCodeStep(current: string | null | undefined, next: string | null | undefined): boolean {
  return next === "aal2" && current !== "aal2";
}

export const CODE_LENGTH = 6;
