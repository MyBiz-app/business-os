import { apiFetch } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

/** Downloads one payslip as a PDF, built by the API. */
export async function GET(request: Request) {
  const { tenant } = await getTenantFor("payroll.read");
  const url = new URL(request.url);
  const month = url.searchParams.get("month") ?? "";
  const user = url.searchParams.get("user") ?? "";
  const version = url.searchParams.get("version");
  if (version !== null && !/^\d{1,3}$/.test(version)) return new Response(null, { status: 400 });
  if (!/^\d{4}-\d{2}$/.test(month) || !/^[0-9a-f-]{36}$/i.test(user)) return new Response(null, { status: 400 });
  const response = await apiFetch(`/payroll/runs/${month}/payslips/${user}/pdf${version === null ? "" : `?version=${version}`}`, { method: "GET" }, tenant.id);
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
