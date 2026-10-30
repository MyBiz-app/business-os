import { createApiClient, type ApiClient } from "@business-os/api-client";

import { API_URL } from "./env";
import { isNetworkFailure, setOnline } from "./connection";
import { queryClient } from "./query-client";
import { supabase } from "./supabase";

export { API_URL };

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string | undefined,
  ) {
    super(`API ${status}: ${detail ?? "error"}`);
  }
}

/** Calls the app makes by itself, which change nothing a screen shows. */
const BACKGROUND_PATHS = /^\/me\/(devices|push-tokens)/;

/** A typed API client that signs requests as the current user. */
export function apiClient(): ApiClient {
  const client = createApiClient({ baseUrl: API_URL });
  client.use({
    async onRequest({ request }) {
      const { data } = await supabase.auth.getSession();
      if (data.session) request.headers.set("Authorization", `Bearer ${data.session.access_token}`);
      return request;
    },
    onResponse({ request, response }) {
      setOnline(true);
      // Anything the person changed may show on other screens: their saved copies count as old.
      if (response.ok && request.method !== "GET" && !BACKGROUND_PATHS.test(new URL(request.url).pathname)) {
        void queryClient.invalidateQueries();
      }
      return response;
    },
    onError({ error }) {
      if (isNetworkFailure(error)) setOnline(false);
    },
  });
  return client;
}

/** Returns the data of an API call or throws an ApiError with the API's error code. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || result.data === undefined) {
    const detail = (result.error as { detail?: unknown } | undefined)?.detail;
    throw new ApiError(result.response.status, typeof detail === "string" ? detail : undefined);
  }
  return result.data;
}

export function assetUrl(path: string | null | undefined): string | null {
  return path ? `${API_URL}${path}` : null;
}

export async function isApiHealthy(): Promise<boolean> {
  try {
    const response = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(3000) });
    return response.ok;
  } catch {
    return false;
  }
}
