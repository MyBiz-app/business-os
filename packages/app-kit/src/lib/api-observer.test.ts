import assert from "node:assert/strict";
import { test } from "node:test";

import { createApiClient } from "@business-os/api-client";

import { responseObserver } from "./api-observer.ts";

/** A response that is not an instance of the global `Response`, as the phone's fetch can return. */
function foreignResponse(body: unknown, status = 200) {
  const text = JSON.stringify(body);
  return {
    ok: status < 400,
    status,
    headers: new Headers({ "Content-Length": String(text.length) }),
    json: async () => body,
    text: async () => text,
  } as unknown as Response;
}

function clientAnswering(response: Response, calls: string[]) {
  const client = createApiClient({
    baseUrl: "https://api.test",
    fetch: async () => response,
  });
  client.use(responseObserver({ markOnline: () => calls.push("online"), invalidateAll: () => calls.push("invalidate") }));
  return client;
}

test("an answer from a fetch with its own response class still reaches the caller", async () => {
  const calls: string[] = [];
  const result = await clientAnswering(foreignResponse([{ id: "b1" }]), calls).GET("/client/businesses" as never, {} as never);
  assert.deepEqual(result.data, [{ id: "b1" }]);
  assert.deepEqual(calls, ["online"]);
});

test("a change that succeeded makes saved copies old", async () => {
  const calls: string[] = [];
  await clientAnswering(foreignResponse({ ok: true }), calls).POST("/client/bookings" as never, {} as never);
  assert.deepEqual(calls, ["online", "invalidate"]);
});

test("background calls and failed changes leave saved copies alone", async () => {
  const calls: string[] = [];
  await clientAnswering(foreignResponse({}), calls).POST("/me/push-tokens" as never, {} as never);
  await clientAnswering(foreignResponse({ detail: "no" }, 409), calls).POST("/client/bookings" as never, {} as never);
  assert.deepEqual(calls, ["online", "online"]);
});
