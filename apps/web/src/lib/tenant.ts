import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { getApi, unwrap } from "@/lib/api";

export const TENANT_COOKIE = "TENANT_ID";

/** The signed-in user and the business they are working in (null if they have none yet). */
export const getActiveMembership = cache(async () => {
  const me = unwrap(await (await getApi()).GET("/me"));
  const selected = (await cookies()).get(TENANT_COOKIE)?.value;
  const membership =
    me.memberships.find((m) => m.tenant_id === selected) ?? me.memberships[0] ?? null;
  return { me, membership };
});

/** The active business, its API client and the header that scopes requests to it. */
export const getTenant = cache(async () => {
  const { me, membership } = await getActiveMembership();
  if (!membership) redirect("/onboarding");

  const api = await getApi();
  const scope = { header: { "X-Tenant-Id": membership.tenant_id } };
  const tenant = unwrap(await api.GET("/tenants/current", { params: scope }));
  return { me, tenant, api, scope };
});

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
