import "server-only";

import { headers } from "next/headers";

/** The public origin of this request, e.g. https://example.vercel.app. */
export async function siteOrigin(): Promise<string> {
  const headerList = await headers();
  const host = headerList.get("x-forwarded-host") ?? headerList.get("host");
  const protocol = headerList.get("x-forwarded-proto") ?? "http";
  return `${protocol}://${host}`;
}
