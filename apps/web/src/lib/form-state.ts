import { ApiError } from "@/lib/api";

export type FormState = { error?: "invalid" | "generic"; saved?: boolean };

export function errorState(error: unknown): FormState {
  return { error: error instanceof ApiError && error.status === 422 ? "invalid" : "generic" };
}
