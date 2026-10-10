import { apiFetch } from "@/lib/api";
import { getTenant } from "@/lib/tenant";

/** The business's cover image, for its own team (the `?v=` in the URL changes with it). */
export async function GET() {
  const { tenant } = await getTenant();
  const response = await apiFetch("/tenants/current/cover", { method: "GET" }, tenant.id);
  if (!response.ok) return new Response(null, { status: response.status === 404 ? 404 : 502 });
  return new Response(await response.arrayBuffer(), {
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/octet-stream",
      "Cache-Control": "private, max-age=31536000, immutable",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
