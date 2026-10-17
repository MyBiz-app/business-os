import { apiFetch } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

/** Downloads an issued document: the stored original, or with `?copy=1` a copy marked as such. */
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const copy = new URL(request.url).searchParams.get("copy") === "1";
  const { tenant } = await getTenantFor("sales.manage");
  const response = await apiFetch(
    `/issued-documents/${encodeURIComponent(id)}.pdf${copy ? "?copy=true" : ""}`,
    { method: "GET" },
    tenant.id,
  );
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
