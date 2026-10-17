/** Two-step sign-in and idle timeout helpers, shared by the proxy, the pages and the browser. */

/** The web app signs people out after this long without activity. */
export const INACTIVITY_LIMIT_MS = 12 * 60 * 60 * 1000;
/** The cookie names carry `app.cookiePrefix` of brand.json; a brand test checks they still match
 * (this file is also run by plain Node tests, which cannot import the JSON file). */
/** A timestamp (ms) of the person's last click or key press; read by the proxy. */
export const ACTIVITY_COOKIE = "bos_active";
/** A random id of this browser, kept so a sign-in from a new one can be emailed to the person. */
export const DEVICE_COOKIE = "bos_device";
export const MFA_PAGE = "/login/mfa";
export const CODE_LENGTH = 6;

/** Whether the activity stamp is older than the limit. No stamp counts as active (first request). */
export function isInactive(stamp: string | undefined, now: number, limit = INACTIVITY_LIMIT_MS): boolean {
  if (!stamp) return false;
  const last = Number(stamp);
  return Number.isFinite(last) && now - last > limit;
}

/** The person has an authenticator but has not entered a code in this session yet. */
export function needsCodeStep(current: string | null | undefined, next: string | null | undefined): boolean {
  return next === "aal2" && current !== "aal2";
}

/** Staging demo owners listed in MFA_DEMO_EXEMPT_EMAILS (comma-separated) skip the code step.
 * Unset everywhere else; the API applies the same list only on staging. */
export function isMfaExempt(email: string | null | undefined, list = process.env.MFA_DEMO_EXEMPT_EMAILS): boolean {
  if (!email || !list) return false;
  return list.split(",").some((entry) => entry.trim().toLowerCase() === email.trim().toLowerCase());
}

export function isCode(value: string): boolean {
  return new RegExp(`^\\d{${CODE_LENGTH}}$`).test(value);
}

/** "Chrome on Windows" from a User-Agent header. Only what a person needs to recognise the device. */
export function deviceLabel(userAgent: string): string {
  const browser = /Edg\//.test(userAgent)
    ? "Edge"
    : /OPR\/|Opera/.test(userAgent)
      ? "Opera"
      : /Firefox\//.test(userAgent)
        ? "Firefox"
        : /Chrome\/|CriOS\//.test(userAgent)
          ? "Chrome"
          : /Safari\//.test(userAgent)
            ? "Safari"
            : "Browser";
  const system = /iPhone|iPad/.test(userAgent)
    ? "iOS"
    : /Android/.test(userAgent)
      ? "Android"
      : /Windows/.test(userAgent)
        ? "Windows"
        : /Mac OS X|Macintosh/.test(userAgent)
          ? "macOS"
          : /Linux/.test(userAgent)
            ? "Linux"
            : "";
  return system ? `${browser} on ${system}` : browser;
}
