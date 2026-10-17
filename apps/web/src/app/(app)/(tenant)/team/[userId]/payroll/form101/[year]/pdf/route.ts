import { apiFetch } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

/** Downloads a signed Form 101 as a PDF, rendered by the API. */
export async function GET(_request: Request, { params }: { params: Promise<{ userId: string; year: string }> }) {
  const { userId, year } = await params;
  const { tenant } = await getTenantFor("payroll.read");
  const response = await apiFetch(
    `/staff/${encodeURIComponent(userId)}/form101/${encodeURIComponent(year)}/pdf`,
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
