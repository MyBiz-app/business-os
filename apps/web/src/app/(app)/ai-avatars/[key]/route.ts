import { cookies } from "next/headers";

import { apiFetch } from "@/lib/api";
import { getActiveMembership, TENANT_COOKIE } from "@/lib/tenant";

/** An AI agent's uploaded picture for the current business (the API checks the person may use
 * the AI team). The `?v=` in the URL changes with the picture. */
export async function GET(_request: Request, { params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const { me } = await getActiveMembership();
  const tenantId = (await cookies()).get(TENANT_COOKIE)?.value ?? me.memberships[0]?.tenant_id ?? "";
  const response = await apiFetch(`/ai/agents/${encodeURIComponent(key)}/avatar`, { method: "GET" }, tenantId);
  if (!response.ok) return new Response(null, { status: response.status === 404 ? 404 : 502 });
  return new Response(await response.arrayBuffer(), {
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/octet-stream",
      "Cache-Control": "private, max-age=31536000, immutable",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
