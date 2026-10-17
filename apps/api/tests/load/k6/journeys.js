// Parallel load on the five busiest business journeys (GL18).
//
//   k6 run -e BASE_URL=http://127.0.0.1:8000 -e TENANT_ID=... -e TOKEN=... -e VUS=100 journeys.js
//
// VUS is the number of people using the app at once (the plan: 50, 100 and 200). Each virtual
// person loops through the five journeys with a short think time. Run it against a local stack
// (tests/load/local_stack.py) or against staging at night, never against production.
// The business ceiling (API_TENANT_RATE_LIMIT_PER_MINUTE) and the address limits are meant for
// real traffic; a single-business test needs them off or raised (local development has them off).
import http from "k6/http";
import { check, group, sleep } from "k6";
import { Trend } from "k6/metrics";

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8000";
const VUS = parseInt(__ENV.VUS || "50", 10);
const DURATION = __ENV.DURATION || "2m";
const headers = {
  Authorization: `Bearer ${__ENV.TOKEN}`,
  "X-Tenant-Id": __ENV.TENANT_ID,
  "Content-Type": "application/json",
};

const journeys = ["timetable", "booking", "shifts", "client_card", "dashboard"];
const trends = {};
for (const name of journeys) trends[name] = new Trend(`journey_${name}`, true);

export const options = {
  scenarios: {
    people: {
      executor: "ramping-vus",
      stages: [
        { duration: "20s", target: VUS },
        { duration: DURATION, target: VUS },
        { duration: "10s", target: 0 },
      ],
    },
  },
  thresholds: {
    // Server errors and the business ceiling are failures; a booking that is full is not.
    "http_req_failed{expected_response:true}": ["rate<0.01"],
    checks: ["rate>0.99"],
    http_req_duration: ["p(95)<2000"],
  },
};

const today = new Date().toISOString().slice(0, 10);
const endDay = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
const startDay = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);

function get(path, params) {
  // A list value repeats the parameter (keys=a&keys=b), as the API expects.
  const pairs = [];
  for (const [k, v] of Object.entries(params || {})) {
    for (const item of Array.isArray(v) ? v : [v]) pairs.push(`${k}=${encodeURIComponent(item)}`);
  }
  const query = pairs.length ? "?" + pairs.join("&") : "";
  return http.get(`${BASE}${path}${query}`, { headers });
}

function ok(response, name) {
  return check(response, { [`${name} 200`]: (r) => r.status === 200 });
}

export function setup() {
  const sessions = get("/sessions", { start: today, days: 14 }).json();
  const clients = (get("/clients", { limit: 200 }).json() || {}).items;
  if (!Array.isArray(sessions) || !sessions.length || !Array.isArray(clients) || !clients.length) {
    throw new Error("setup found no sessions or clients: check TENANT_ID and TOKEN");
  }
  return {
    sessions: sessions.map((s) => s.id),
    clients: clients.map((c) => c.id),
  };
}

const pick = (list) => list[Math.floor(Math.random() * list.length)];

function timetable() {
  const start = new Date(Date.now() + Math.floor(Math.random() * 7) * 86400000);
  ok(get("/sessions", { start: start.toISOString().slice(0, 10), days: 7 }), "timetable");
}

function booking(data) {
  // Staff book a client into a class and take the booking back, so the data keeps its shape.
  const session = pick(data.sessions);
  const response = http.post(
    `${BASE}/sessions/${session}/bookings`,
    JSON.stringify({ client_id: pick(data.clients) }),
    { headers },
  );
  // 201 booked; 409 the client already has a spot or the class is closed: both are normal.
  check(response, { "booking handled": (r) => r.status === 201 || r.status === 409 });
  if (response.status === 201) {
    http.patch(
      `${BASE}/bookings/${response.json().id}`,
      JSON.stringify({ status: "cancelled" }),
      { headers },
    );
  }
}

function shifts() {
  ok(get("/shifts", { start: today, days: 7 }), "shifts");
}

function clientCard(data) {
  const id = pick(data.clients);
  ok(get(`/clients/${id}`), "client");
  ok(get(`/clients/${id}/bookings`), "client bookings");
}

function dashboard() {
  ok(get("/attention"), "attention");
  ok(get("/resources"), "resources");
  ok(get("/services", { active: "true" }), "services");
  ok(get("/billing/usage"), "usage");
  ok(
    get("/metrics", {
      start: startDay,
      end: endDay,
      keys: ["revenue", "active_clients", "attendance"],
    }),
    "metrics",
  );
}

export default function (data) {
  const steps = { timetable, booking, shifts, client_card: clientCard, dashboard };
  for (const name of journeys) {
    group(name, () => {
      const started = Date.now();
      steps[name](data);
      trends[name].add(Date.now() - started);
    });
    sleep(0.5 + Math.random());
  }
}

export function handleSummary(data) {
  const rows = journeys.map((name) => {
    const m = data.metrics[`journey_${name}`];
    return m ? `| ${name} | ${m.values["p(95)"].toFixed(0)} | ${m.values.max.toFixed(0)} |` : "";
  });
  const text = [
    `VUS=${VUS}  requests=${data.metrics.http_reqs.values.count}  ` +
      `rate=${data.metrics.http_reqs.values.rate.toFixed(1)}/s  ` +
      `p95=${data.metrics.http_req_duration.values["p(95)"].toFixed(0)}ms  ` +
      `failed=${(data.metrics.http_req_failed.values.rate * 100).toFixed(2)}%`,
    "",
    "| journey | p95 ms | worst ms |",
    "|---|---|---|",
    ...rows,
  ].join("\n");
  const out = { stdout: text + "\n" };
  if (__ENV.SUMMARY_FILE) out[__ENV.SUMMARY_FILE] = text + "\n";
  return out;
}
