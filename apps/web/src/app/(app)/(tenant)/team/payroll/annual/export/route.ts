import { apiFetch } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

/** Downloads the yearly summary (Excel or CSV), built by the API. Owner only. */
export async function GET(request: Request) {
  const { tenant } = await getTenantFor("payroll.approve");
  const url = new URL(request.url);
  const year = url.searchParams.get("year") ?? "";
  const format = url.searchParams.get("format") === "csv" ? "csv" : "xlsx";
  if (!/^\d{4}$/.test(year)) return new Response(null, { status: 400 });
  const response = await apiFetch(`/payroll/annual/${year}/export?format=${format}`, { method: "GET" }, tenant.id);
  if (!response.ok) return new Response(null, { status: response.status });
  return new Response(await response.arrayBuffer(), {
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/octet-stream",
      "Content-Disposition": response.headers.get("content-disposition") ?? "attachment",
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
