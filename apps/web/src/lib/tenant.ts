import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { getApi, unwrap } from "@/lib/api";

export const TENANT_COOKIE = "TENANT_ID";
/** The current branch, remembered per business (none: all branches). */
export const branchCookie = (tenantId: string) => `BRANCH_${tenantId}`;

type Scope = { header: { "X-Tenant-Id": string; "X-Location-Id"?: string } };

/** The signed-in user and the business they are working in (null if they have none yet). */
export const getActiveMembership = cache(async () => {
  const me = unwrap(await (await getApi()).GET("/me"));
  const selected = (await cookies()).get(TENANT_COOKIE)?.value;
  // Platform support inside a business that granted access (read-only, audited by the API).
  const support = me.support_access.find((g) => g.tenant_id === selected);
  // MyBiz staff working inside a business for its owner: not a member, and no grant needed;
  // the API checks the permission and audits every request.
  const asPlatform = selected && me.platform_admin ? { tenant_id: selected, tenant_name: "", role: "platform" as const } : null;
  const membership =
    me.memberships.find((m) => m.tenant_id === selected) ??
    (support
      ? {
          tenant_id: support.tenant_id,
          tenant_name: support.tenant_name,
          role: "support" as const,
        }
      : null) ??
    asPlatform ??
    me.memberships[0] ??
    null;
  return { me, membership };
});

const scopeOf = (tenantId: string, branch?: string): Scope => ({
  header: {
    "X-Tenant-Id": tenantId,
    ...(branch ? { "X-Location-Id": branch } : {}),
  },
});
// One request per page render for each business and branch, whoever asks first.
const fetchCurrent = cache(async (tenantId: string, branch?: string) =>
  (await getApi()).GET("/tenants/current", {
    params: scopeOf(tenantId, branch),
  }),
);
const fetchLocations = cache(async (tenantId: string, branch?: string) => (await getApi()).GET("/locations", { params: scopeOf(tenantId, branch) }));

/** The active business, its API client and the headers that scope requests to it and to the
 * current branch (lists, numbers and new records follow it; the API checks it). */
export const getTenant = cache(async () => {
  // The business remembered in the cookie is almost always the one that opens, so its details
  // and branches are requested together with the person's profile instead of after it. The API
  // checks membership on each request, so a stale cookie only costs a wasted call.
  const store = await cookies();
  const remembered = store.get(TENANT_COOKIE)?.value;
  if (remembered) {
    const branch = store.get(branchCookie(remembered))?.value;
    fetchCurrent(remembered, branch).catch(() => undefined);
    fetchLocations(remembered, branch).catch(() => undefined);
  }

  const { me, membership } = await getActiveMembership();
  if (!membership) redirect("/welcome");

  const api = await getApi();
  const branch = store.get(branchCookie(membership.tenant_id))?.value;
  let scope = scopeOf(membership.tenant_id, branch);
  let response = await fetchCurrent(membership.tenant_id, branch);
  if (response.error && branch) {
    // A branch that no longer belongs to the business: fall back to all branches.
    scope = scopeOf(membership.tenant_id);
    response = await fetchCurrent(membership.tenant_id);
  }
  const tenant = unwrap(response);
  return {
    me,
    tenant,
    api,
    scope,
    branch: scope.header["X-Location-Id"] ?? null,
  };
});

/** The business's active branches with their rooms (empty without catalog rights). */
const getActiveLocations = cache(async () => {
  const { tenant, branch } = await getTenant();
  if (!tenant.permissions.includes("catalog.read")) return [];
  return ((await fetchLocations(tenant.id, branch ?? undefined)).data ?? []).filter((b) => b.active);
});

export const getBranches = cache(async () => (await getActiveLocations()).map(({ id, name }) => ({ id, name })));

/** Whether the business rents out courts or rooms by the hour (an active bookable room). */
export const hasBookableRooms = cache(async () => (await getActiveLocations()).some((branch) => branch.rooms.some((room) => room.active && room.bookable)));

export async function setActiveBranch(tenantId: string, branchId: string | null) {
  const store = await cookies();
  if (!branchId) store.delete(branchCookie(tenantId));
  else
    store.set(branchCookie(tenantId), branchId, {
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
      sameSite: "lax",
      httpOnly: true,
    });
}

export async function setActiveTenant(tenantId: string) {
  (await cookies()).set(TENANT_COOKIE, tenantId, {
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
    sameSite: "lax",
    httpOnly: true,
  });
}

/** Like getTenant, but sends the user to the dashboard when their permissions don't cover this
 * page (e.g. a custom role opening a link directly). The API would refuse anyway. */
export async function getTenantFor(permission: string) {
  const context = await getTenant();
  if (!context.tenant.permissions.includes(permission)) redirect("/dashboard");
  return context;
}

export async function clearActiveTenant() {
  (await cookies()).delete(TENANT_COOKIE);
}
