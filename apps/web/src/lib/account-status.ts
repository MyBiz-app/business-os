/** The account status: what is worth completing in the person's own account, shown as a dot by
 * their picture and a card on the home page instead of banners on every page (CRM Premium W2-1).
 * Pure, so plain Node tests can run it. */

/** `mfa_required`: the MyBiz team, who must turn two-step sign-in on (no snooze, no opt-out).
 * `mfa`: an owner or manager without it, who may turn it on, snooze it or decline it.
 * `address`: a team member without a home address, which is optional and can be skipped. */
export type AccountStatusItem = "mfa_required" | "mfa" | "address";

export type AccountStatusInput = {
  /** On the MyBiz team. */
  platform: boolean;
  /** The person's roles in their businesses. */
  roles: string[];
  /** Two-step sign-in is enforced on this server (off in local development). */
  mfaEnforced: boolean;
  /** The person has an authenticator app set up. */
  hasAuthenticator: boolean;
  /** They confirmed the warning ("I don't want two-step sign-in"): no more reminders. */
  riskAcknowledged: boolean;
  /** "Remind me in a week": ISO time until which two-step sign-in is left out. */
  snoozedUntil: string | null | undefined;
  addressComplete: boolean;
  addressSkipped: boolean;
  /** Now, in milliseconds. */
  now: number;
};

export function accountStatusItems(input: AccountStatusInput): AccountStatusItem[] {
  const items: AccountStatusItem[] = [];
  const managerial = input.roles.some((role) => role === "owner" || role === "manager");
  if (input.mfaEnforced && !input.hasAuthenticator) {
    if (input.platform) items.push("mfa_required");
    else if (managerial && !input.riskAcknowledged && !snoozed(input.snoozedUntil, input.now)) items.push("mfa");
  }
  if (input.roles.length > 0 && !input.addressComplete && !input.addressSkipped) items.push("address");
  return items;
}

function snoozed(until: string | null | undefined, now: number): boolean {
  if (!until) return false;
  const time = Date.parse(until);
  return Number.isFinite(time) && time > now;
}

/** The cookie that remembers the person closed the home page card, and for which items: a new
 * item brings the card back. Carries `app.cookiePrefix` of brand.json. */
export const STATUS_CARD_COOKIE = "bos_status_card";

export function itemsKey(items: AccountStatusItem[]): string {
  return [...items].sort().join(".");
}

/** The card stays closed while the items are the ones it was closed with (or fewer of them). */
export function cardDismissed(items: AccountStatusItem[], cookie: string | undefined): boolean {
  if (!cookie) return false;
  const closed = new Set(cookie.split("."));
  return items.every((item) => closed.has(item));
}

/** Where a refused sensitive action sends the person: the same page with `mfa=ack`, which opens the
 * warning window there. Null when the page already asks (so a page that keeps being refused can't
 * loop). */
export function riskPromptUrl(pathname: string, search: string): string | null {
  const params = new URLSearchParams(search);
  if (params.get("mfa") === "ack") return null;
  params.set("mfa", "ack");
  return `${pathname}?${params}`;
}

/** The page without the `mfa` parameter, once the window is closed. */
export function withoutRiskPrompt(pathname: string, search: string): string {
  const params = new URLSearchParams(search);
  params.delete("mfa");
  const rest = params.toString();
  return rest ? `${pathname}?${rest}` : pathname;
}
