/** Solo mode: a business that signed up as one person sees a smaller menu and a simple dashboard.
 * It ends by itself when the first employee or a second branch is added (the API moves the size
 * on), or when the owner presses "I grew" in the settings. */
export const isSolo = (tenant: { business_size?: string | null }) => tenant.business_size === "solo";

/** In solo mode the menu offers at most this many locked modules ("upgrade" suggestions). */
export const SOLO_MAX_UPGRADES = 2;

/** The simple dashboard: this period's income and new clients, and who has not come back. */
export const SOLO_DASHBOARD_TILES = ["revenue", "new_clients", "active_clients"] as const;
export const SOLO_ATTENTION = ["inactive"] as const;
