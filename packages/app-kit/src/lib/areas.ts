// The one MyBiz app serves every identity a person has. Each identity is an "area": the MyBiz
// team, a business they work in (as owner, manager, staff or front desk), or a business they
// are a client of. Pure logic only, so it can be tested without a phone.

export type AreaKind = "platform" | "business" | "client";

export type BusinessRole = "owner" | "manager" | "branch_manager" | "staff" | "front_desk";

export type Area = {
  /** Stable id: `platform`, `business:<tenant>` or `client:<tenant>`. */
  key: string;
  kind: AreaKind;
  tenantId?: string;
  name: string;
  role?: BusinessRole;
  /** A team member's client area of their own business that they have not opened yet: their
   * client card is made the first time they open it, so unused areas add no clients. */
  joinOnOpen?: boolean;
};

type AreaInput = {
  platformAdmin: boolean;
  memberships: { tenant_id: string; tenant_name: string; role: BusinessRole; client_app?: boolean }[];
  businesses: { id: string; name: string }[];
  /** The product's name, shown for the team area (the caller passes BRAND.name). */
  platformName?: string;
};

export function buildAreas({ platformAdmin, memberships, businesses, platformName = "" }: AreaInput): Area[] {
  const areas: Area[] = [];
  if (platformAdmin) areas.push({ key: "platform", kind: "platform", name: platformName });
  for (const m of memberships) {
    areas.push({ key: `business:${m.tenant_id}`, kind: "business", tenantId: m.tenant_id, name: m.tenant_name, role: m.role });
  }
  for (const b of businesses) {
    areas.push({ key: `client:${b.id}`, kind: "client", tenantId: b.id, name: b.name });
  }
  // Everyone who works in a business can also be its client.
  for (const m of memberships) {
    if (!m.client_app || businesses.some((b) => b.id === m.tenant_id)) continue;
    areas.push({ key: `client:${m.tenant_id}`, kind: "client", tenantId: m.tenant_id, name: m.tenant_name, joinOnOpen: true });
  }
  return areas;
}

/** The area to open: the last one used, else the first area whose screens already live in this
 * app (`ready`), else the first. Never one still to be joined: that takes a tap in the switcher.
 * Null when the person has no area (they join a business). */
export function pickArea(areas: Area[], storedKey: string | null, ready: readonly AreaKind[]): Area | null {
  const open = areas.filter((a) => !a.joinOnOpen);
  return open.find((a) => a.key === storedKey) ?? open.find((a) => ready.includes(a.kind)) ?? open[0] ?? null;
}

/** Where an area starts. */
export function areaHome(area: Area): "/home" | "/business" | "/platform" {
  return area.kind === "client" ? "/home" : area.kind === "business" ? "/business" : "/platform";
}
