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

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {
    super(`API request failed with status ${status}`);
  }
}

/** A typed API client that calls the backend as the signed-in user. */
export async function getApi(): Promise<ApiClient> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const headers: Record<string, string> = {};
  if (session) headers.Authorization = `Bearer ${session.access_token}`;

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
