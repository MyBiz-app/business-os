import { type NextRequest, NextResponse } from "next/server";

import { apiFetch } from "@/lib/api";

/** City suggestions for the address picker: the API's official list, for any signed-in person. */
export async function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams;
  const params = new URLSearchParams({ q: query.get("q") ?? "", limit: query.get("limit") ?? "12" });
  const response = await apiFetch(`/geo/cities?${params}`, { method: "GET" }, "");
  if (!response.ok) return new NextResponse(null, { status: response.status === 401 ? 401 : 502 });
  return NextResponse.json(await response.json(), { headers: { "Cache-Control": "private, max-age=3600" } });
}
