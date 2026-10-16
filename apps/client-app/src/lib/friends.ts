import type { components } from "@business-os/api-client";

export type Person = components["schemas"]["Person"];

const KNOWN = [
  "already_friends",
  "already_invited",
  "already_requested",
  "invite_expired",
  "invite_window_closed",
  "not_booked",
  "session_cancelled",
  "session_full",
  "friends_disabled",
  "friends_rate_limited",
  "not_found",
] as const;

/** The API's error code for a failed friends call, when it is one we have a message for. */
export function friendsError(error: unknown): (typeof KNOWN)[number] | "generic" {
  const detail = (error as { detail?: string } | undefined)?.detail;
  return KNOWN.includes(detail as (typeof KNOWN)[number]) ? (detail as (typeof KNOWN)[number]) : "generic";
}

/** Full name for friends (the API only sends the last name to them), first name for the rest. */
export function personName(person: Pick<Person, "first_name" | "last_name">): string {
  return [person.first_name, person.last_name].filter(Boolean).join(" ");
}
