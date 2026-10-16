import { apiFetch } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

/** Downloads a receipt as a PDF, rendered by the API in the business's brand frame. */
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { tenant } = await getTenantFor("clients.read");
  const response = await apiFetch(`/documents/render/receipt/${encodeURIComponent(id)}.pdf`, { method: "GET" }, tenant.id);
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
