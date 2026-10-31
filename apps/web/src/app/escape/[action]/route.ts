import { NextResponse, type NextRequest } from "next/server";

import { createClient } from "@/lib/supabase/server";
import { TENANT_COOKIE } from "@/lib/tenant";

/** Ways out of a broken screen. Plain form posts, so they work even when the page itself failed:
 * `sign-out` ends the session and opens the public site; `switch-business` forgets the remembered
 * business and opens the list of the person's businesses. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ action: string }> }) {
  const { action } = await params;
  if (action === "sign-out") {
    await (await createClient()).auth.signOut();
    return NextResponse.redirect(new URL("/?signed_out=1", request.url), 303);
  }
  if (action === "switch-business") {
    const response = NextResponse.redirect(new URL("/businesses", request.url), 303);
    response.cookies.delete(TENANT_COOKIE);
    return response;
  }
  return new NextResponse(null, { status: 404 });
}
