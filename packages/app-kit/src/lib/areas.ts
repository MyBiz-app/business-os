// The one MyBiz app serves every identity a person has. Each identity is an "area": the MyBiz
// team, a business they work in (as owner, manager, staff or front desk), or a business they
// are a client of. Pure logic only, so it can be tested without a phone.

export type AreaKind = "platform" | "business" | "client";

export type BusinessRole = "owner" | "manager" | "staff" | "front_desk";

export type Area = {
  /** Stable id: `platform`, `business:<tenant>` or `client:<tenant>`. */
  key: string;
  kind: AreaKind;
  tenantId?: string;
  name: string;
  role?: BusinessRole;
};

type AreaInput = {
  platformAdmin: boolean;
  memberships: { tenant_id: string; tenant_name: string; role: BusinessRole }[];
  businesses: { id: string; name: string }[];
};

export function buildAreas({ platformAdmin, memberships, businesses }: AreaInput): Area[] {
  const areas: Area[] = [];
  if (platformAdmin) areas.push({ key: "platform", kind: "platform", name: "MyBiz" });
  for (const m of memberships) {
    areas.push({ key: `business:${m.tenant_id}`, kind: "business", tenantId: m.tenant_id, name: m.tenant_name, role: m.role });
  }
  for (const b of businesses) {
    areas.push({ key: `client:${b.id}`, kind: "client", tenantId: b.id, name: b.name });
  }
  return areas;
}

/** The area to open: the last one used, else the first area whose screens already live in this
 * app (`ready`), else the first. Null when the person has no area (they join a business). */
export function pickArea(areas: Area[], storedKey: string | null, ready: readonly AreaKind[]): Area | null {
  return (
    areas.find((a) => a.key === storedKey) ?? areas.find((a) => ready.includes(a.kind)) ?? areas[0] ?? null
  );
}

/** Where an area starts. */
export function areaHome(area: Area): "/home" | "/business" | "/platform" {
  return area.kind === "client" ? "/home" : area.kind === "business" ? "/business" : "/platform";
}
