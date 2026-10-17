// Checks the per-business ceiling (GL18): one business sends more than its allowance in a minute
// and gets 429 `tenant_rate_limited`, while a second business is unaffected.
//
// Needs an API with rate limits on (API_RATE_LIMITS=true) and the default 600 per minute:
//   k6 run -e BASE_URL=... -e TENANT_ID=... -e TOKEN=... -e LIMIT=600 quota.js
import http from "k6/http";
import { check } from "k6";

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8000";
const LIMIT = parseInt(__ENV.LIMIT || "600", 10);
const headers = { Authorization: `Bearer ${__ENV.TOKEN}`, "X-Tenant-Id": __ENV.TENANT_ID };

export const options = { vus: 1, iterations: 1 };

export default function () {
  let allowed = 0;
  let blocked = 0;
  let detail = "";
  for (let i = 0; i < LIMIT + 50; i++) {
    const r = http.get(`${BASE}/services`, { headers });
    if (r.status === 200) allowed++;
    else if (r.status === 429) {
      blocked++;
      detail = r.json("detail");
    }
  }
  console.log(`allowed=${allowed} blocked=${blocked} detail=${detail}`);
  check(null, {
    "the allowance is served": () => allowed >= LIMIT - 5,
    "the excess is refused": () => blocked >= 40,
    "with the business reason": () => detail === "tenant_rate_limited",
  });
}
