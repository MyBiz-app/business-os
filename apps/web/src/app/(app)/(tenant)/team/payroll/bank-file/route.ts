import { apiFetch } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

/** Creates the Masav bank file of an approved month (owner only) and returns it as a download.
 *  Nothing is sent to a bank. */
export async function POST(request: Request) {
  const origin = request.headers.get("origin");
  if (origin && new URL(origin).host !== request.headers.get("host")) return new Response(null, { status: 403 });
  const { tenant } = await getTenantFor("payroll.approve");
  const form = await request.formData();
  const month = String(form.get("month") ?? "");
  if (!/^\d{4}-\d{2}$/.test(month)) return new Response(null, { status: 400 });
  const response = await apiFetch(
    `/payroll/runs/${month}/bank-file`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        institution_code: String(form.get("institution_code") ?? ""),
        sending_code: String(form.get("sending_code") ?? ""),
        institution_name: String(form.get("institution_name") ?? ""),
        pay_date: String(form.get("pay_date") ?? ""),
      }),
    },
    tenant.id,
  );
  if (!response.ok) return new Response(null, { status: response.status === 422 ? 422 : 502 });
  return new Response(await response.arrayBuffer(), {
    headers: {
      "Content-Type": "text/plain; charset=cp862",
      "Content-Disposition": response.headers.get("content-disposition") ?? "attachment",
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
