/** How long the app may stay in the background before it locks again. */
export const LOCK_TIMEOUTS = ["immediate", "30s", "5m"] as const;
export type LockTimeout = (typeof LOCK_TIMEOUTS)[number];

export const DEFAULT_LOCK_TIMEOUT: LockTimeout = "30s";

const TIMEOUT_MS: Record<LockTimeout, number> = { immediate: 0, "30s": 30_000, "5m": 300_000 };

/** The app locks again after being in the background for this long (the default timeout). */
export const LOCK_AFTER_MS = TIMEOUT_MS[DEFAULT_LOCK_TIMEOUT];

/** Reads a stored value; anything unknown falls back to the default. */
export function parseLockTimeout(value: string | null | undefined): LockTimeout {
  return LOCK_TIMEOUTS.find((option) => option === value) ?? DEFAULT_LOCK_TIMEOUT;
}

/** Whether the app must be locked on coming back to the foreground. */
export function shouldLock(enabled: boolean, backgroundedAt: number | null, now: number, timeout: LockTimeout = DEFAULT_LOCK_TIMEOUT): boolean {
  return enabled && backgroundedAt !== null && now - backgroundedAt >= TIMEOUT_MS[timeout];
}

/** Offer Face ID / fingerprint once: only when the phone supports it, the lock was never decided on, and the offer was not shown yet. */
export function shouldOfferLock(supported: boolean, decided: boolean, offered: boolean): boolean {
  return supported && !decided && !offered;
}

/** The first letter of a name or email, for the avatar on the lock screen. */
export function initialOf(name: string | null | undefined): string {
  const first = (name ?? "").trim().charAt(0);
  return first ? first.toLocaleUpperCase() : "?";
}
