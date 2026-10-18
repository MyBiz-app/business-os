import { NextResponse } from "next/server";

import { getPlatformFor } from "@/lib/platform";

/** The images and logo of an order, as one ZIP (passed through from the API). */
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { api } = await getPlatformFor("businesses.act");
  const { response } = await api.GET("/platform/website-orders/{order_id}/files.zip", { params: { path: { order_id: id } }, parseAs: "stream" });
  if (!response.ok) return new NextResponse(null, { status: response.status });
  return new NextResponse(response.body, {
    headers: { "Content-Type": "application/zip", "Content-Disposition": 'attachment; filename="website-files.zip"', "Cache-Control": "private, no-store" },
  });
}
