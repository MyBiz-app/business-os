import { createApiClient, type ApiClient } from "@business-os/api-client";

import { API_URL } from "@/lib/env";
import { supabase } from "@/lib/supabase";

export { API_URL };

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string | undefined,
  ) {
    super(`API ${status}: ${detail ?? "error"}`);
  }
}

/** A typed API client that signs requests as the current user. */
export function apiClient(): ApiClient {
  const client = createApiClient({ baseUrl: API_URL });
  client.use({
    async onRequest({ request }) {
      const { data } = await supabase.auth.getSession();
      if (data.session) request.headers.set("Authorization", `Bearer ${data.session.access_token}`);
      return request;
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
