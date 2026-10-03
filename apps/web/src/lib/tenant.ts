import "server-only";

import { cookies } from "next/headers";

import { getApi, unwrap } from "@/lib/api";

export const TENANT_COOKIE = "TENANT_ID";

/** The signed-in user and the business they are working in (null if they have none yet). */
export async function getActiveMembership() {
  const me = unwrap(await (await getApi()).GET("/me"));
  const selected = (await cookies()).get(TENANT_COOKIE)?.value;
  const membership =
    me.memberships.find((m) => m.tenant_id === selected) ?? me.memberships[0] ?? null;
  return { me, membership };
}

export async function setActiveTenant(tenantId: string) {
  (await cookies()).set(TENANT_COOKIE, tenantId, {
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
    sameSite: "lax",
    httpOnly: true,
  });
}
