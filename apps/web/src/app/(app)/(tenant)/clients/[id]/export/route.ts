import { apiFetch } from "@/lib/api";
import { getTenant } from "@/lib/tenant";

/** Downloads everything the business holds about the client (privacy request), as JSON. */
export async function GET(_request: Request, { params }: RouteContext<"/clients/[id]/export">) {
  const { id } = await params;
  const { tenant } = await getTenant();
  if (!tenant.permissions.includes("clients.privacy")) return new Response(null, { status: 403 });
  const response = await apiFetch(`/clients/${encodeURIComponent(id)}/export`, { method: "GET" }, tenant.id);
  if (!response.ok) return new Response(null, { status: response.status });
  return new Response(await response.text(), {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Content-Disposition": `attachment; filename="client-${id}.json"`,
      "Cache-Control": "no-store",
    },
  });
}
