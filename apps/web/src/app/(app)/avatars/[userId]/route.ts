import { cookies } from "next/headers";

import { apiFetch } from "@/lib/api";
import { getActiveMembership, TENANT_COOKIE } from "@/lib/tenant";

/** A person's profile picture for the signed-in user: their own, or a teammate's in the
 * current business (the API checks both). The `?v=` in the URL changes with the picture. */
export async function GET(_request: Request, { params }: { params: Promise<{ userId: string }> }) {
  const { userId } = await params;
  const { me } = await getActiveMembership();
  const tenantId = (await cookies()).get(TENANT_COOKIE)?.value ?? me.memberships[0]?.tenant_id ?? "";
  const path = userId === me.id ? "/me/avatar" : `/staff/${encodeURIComponent(userId)}/avatar`;
  const response = await apiFetch(path, { method: "GET" }, tenantId);
  if (!response.ok) return new Response(null, { status: response.status === 404 ? 404 : 502 });
  return new Response(await response.arrayBuffer(), {
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/octet-stream",
      "Cache-Control": "private, max-age=31536000, immutable",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

