import { type NextRequest, NextResponse } from "next/server";

import { API_URL } from "@/lib/api";

/** City suggestions for a form anyone can open (a business's inquiry form): the API's public,
 * rate-limited copy of the official list. Nobody's data is involved. */
export async function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams;
  const params = new URLSearchParams({ q: query.get("q") ?? "", limit: query.get("limit") ?? "12" });
  const response = await fetch(`${API_URL}/public/geo/cities?${params}`, { cache: "no-store" }).catch(() => null);
  if (!response?.ok) return new NextResponse(null, { status: 502 });
  return NextResponse.json(await response.json(), { headers: { "Cache-Control": "public, max-age=3600" } });
}
