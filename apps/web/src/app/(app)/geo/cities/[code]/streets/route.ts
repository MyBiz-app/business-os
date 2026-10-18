import { type NextRequest, NextResponse } from "next/server";

import { apiFetch } from "@/lib/api";

/** Street suggestions inside one city, for the address picker. */
export async function GET(request: NextRequest, { params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  if (!/^\d{1,6}$/.test(code)) return new NextResponse(null, { status: 404 });
  const query = request.nextUrl.searchParams;
  const search = new URLSearchParams({ q: query.get("q") ?? "", limit: query.get("limit") ?? "12" });
  const response = await apiFetch(`/geo/cities/${code}/streets?${search}`, { method: "GET" }, "");
  if (!response.ok) return new NextResponse(null, { status: response.status === 401 ? 401 : 502 });
  return NextResponse.json(await response.json(), { headers: { "Cache-Control": "private, max-age=3600" } });
}
