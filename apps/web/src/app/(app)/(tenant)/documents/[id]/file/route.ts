import { apiFetch } from "@/lib/api";
import { getTenant } from "@/lib/tenant";

/** Downloads a client document as the signed-in staff member (#45). */
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { tenant } = await getTenant();
  const response = await apiFetch(`/documents/${encodeURIComponent(id)}/file`, { method: "GET" }, tenant.id);
  if (!response.ok) return new Response(null, { status: response.status });
  // Buffered (files are at most 10 MB): streaming through breaks when the client hangs up.
  return new Response(await response.arrayBuffer(), {
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/octet-stream",
      "Content-Disposition": response.headers.get("content-disposition") ?? "attachment",
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
