import { apiFetch } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

/** Downloads the audit log (the same filters as the screen) as CSV, built by the API. */
export async function GET(request: Request) {
  const { tenant } = await getTenantFor("staff.manage");
  const source = new URL(request.url).searchParams;
  const query = new URLSearchParams();
  const map = { actor: "actor_id", category: "category", from: "date_from", to: "date_to" } as const;
  for (const [key, name] of Object.entries(map)) {
    const value = source.get(key);
    if (value) query.set(name, value);
  }
  const response = await apiFetch(`/audit-log/export${query.size ? `?${query}` : ""}`, { method: "GET" }, tenant.id);
  if (!response.ok) return new Response(null, { status: response.status });
  return new Response(await response.arrayBuffer(), {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": response.headers.get("content-disposition") ?? "attachment",
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
