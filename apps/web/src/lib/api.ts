import "server-only";

import { type ApiClient, createApiClient } from "@business-os/api-client";

import { createClient } from "@/lib/supabase/server";

export type { Me, Role, Tenant } from "@business-os/api-client";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function isApiHealthy(): Promise<boolean> {
  try {
    const { response } = await createApiClient({ baseUrl: API_URL }).GET("/health", {
      signal: AbortSignal.timeout(2000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

/** Absolute URL for a path served by the API (e.g. a tenant logo). */
export function apiAssetUrl(path: string | null | undefined): string | null {
  return path ? `${API_URL}${path}` : null;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {
    super(`API request failed with status ${status}`);
  }
}

async function authHeaders(): Promise<Record<string, string>> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session ? { Authorization: `Bearer ${session.access_token}` } : {};
}

/** Uploads a file (multipart) to the API as the signed-in user, scoped to a tenant. */
export async function apiUpload(path: string, file: File, tenantId: string): Promise<Response> {
  const body = new FormData();
  body.set("file", file);
  return fetch(`${API_URL}${path}`, {
    method: "PUT",
    headers: { ...(await authHeaders()), "X-Tenant-Id": tenantId },
    body,
    cache: "no-store",
  });
}

/** A raw API request as the signed-in user, for bodies the typed client can't send (files). */
export async function apiFetch(path: string, init: RequestInit, tenantId: string): Promise<Response> {
  return fetch(`${API_URL}${path}`, {
    ...init,
    headers: { ...(await authHeaders()), "X-Tenant-Id": tenantId },
    cache: "no-store",
  });
}

/** A typed API client that calls the backend as the signed-in user. */
export async function getApi(): Promise<ApiClient> {
  const headers = await authHeaders();

  return createApiClient({
    baseUrl: API_URL,
    headers,
    fetch: (request) => fetch(request, { cache: "no-store" }),
  });
}

/** Returns the response data, or throws ApiError for any non-2xx response. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined) throw new ApiError(result.response.status, result.error);
  return result.data;
}
