import { parseCspReports } from "@/lib/csp";

// Browsers post here what the Report-Only policy (lib/csp.ts) would have blocked. One compact
// log line per violation, readable in the Vercel runtime logs; nothing is stored.
const MAX_BODY = 16_000;

export async function POST(request: Request) {
  const text = (await request.text()).slice(0, MAX_BODY);
  let payload: unknown;
  try {
    payload = JSON.parse(text);
  } catch {
    return new Response(null, { status: 204 });
  }
  for (const violation of parseCspReports(payload)) {
    console.warn(`csp-violation ${JSON.stringify(violation)}`);
  }
  return new Response(null, { status: 204 });
}
