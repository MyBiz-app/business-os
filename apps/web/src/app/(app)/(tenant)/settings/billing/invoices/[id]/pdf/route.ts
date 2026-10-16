import { apiFetch } from "@/lib/api";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

/** Downloads a MyBiz invoice as a PDF, rendered by the API with MyBiz's company details. */
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { tenant } = await getTenant();
  if (!canManageSettings(tenant)) return new Response(null, { status: 403 });
  const response = await apiFetch(`/documents/render/platform_invoice/${encodeURIComponent(id)}.pdf`, { method: "GET" }, tenant.id);
  if (!response.ok) return new Response(null, { status: response.status });
  return new Response(await response.arrayBuffer(), {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": response.headers.get("content-disposition") ?? "attachment",
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
