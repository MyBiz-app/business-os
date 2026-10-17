import { apiFetch } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

/** Downloads the month's table for the accountant (Excel or CSV), built by the API. */
export async function GET(request: Request) {
  const { tenant } = await getTenantFor("payroll.read");
  const url = new URL(request.url);
  const month = url.searchParams.get("month") ?? "";
  const format = url.searchParams.get("format") === "csv" ? "csv" : "xlsx";
  if (!/^\d{4}-\d{2}$/.test(month)) return new Response(null, { status: 400 });
  const response = await apiFetch(`/payroll/runs/${month}/export?format=${format}`, { method: "GET" }, tenant.id);
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
