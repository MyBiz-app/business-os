import "server-only";

import { createClient } from "@/lib/supabase/server";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function isApiHealthy(): Promise<boolean> {
  try {
    const response = await fetch(`${API_URL}/health`, {
      cache: "no-store",
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

/** Calls the backend API as the signed-in user. */
export async function apiFetch<T>(
  path: string,
  init: RequestInit & { tenantId?: string } = {},
): Promise<T> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (session) headers.set("Authorization", `Bearer ${session.access_token}`);
  if (init.tenantId) headers.set("X-Tenant-Id", init.tenantId);

  const response = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
  if (!response.ok) {
    throw new ApiError(response.status, await response.json().catch(() => null));
  }
  return (await response.json()) as T;
}

export type Role = "owner" | "manager" | "staff" | "front_desk";

export type Me = {
  id: string;
  email: string;
  full_name: string | null;
  locale: "he" | "en" | null;
  memberships: { tenant_id: string; tenant_name: string; role: Role }[];
};

export type Tenant = {
  id: string;
  name: string;
  vertical: string;
  locale: "he" | "en";
  time_zone: string;
  currency: string;
  role: Role;
};
