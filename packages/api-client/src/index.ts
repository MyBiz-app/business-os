import createClient, { type ClientOptions } from "openapi-fetch";

import type { components, paths } from "./schema";

export type { components, paths };

export type Me = components["schemas"]["Me"];
export type Tenant = components["schemas"]["Tenant"];
export type TenantCreate = components["schemas"]["TenantCreate"];
export type Role = Tenant["role"];

/** A typed client for the Business OS API, generated from its OpenAPI schema. */
export function createApiClient(options: ClientOptions) {
  return createClient<paths>(options);
}

export type ApiClient = ReturnType<typeof createApiClient>;
