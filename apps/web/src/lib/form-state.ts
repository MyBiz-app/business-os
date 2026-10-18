import { ApiError } from "@/lib/api";

export type FormState = { error?: "invalid" | "generic" | "storage_full"; saved?: boolean;
  /** Where a window over a list goes once the form is saved (instead of the action redirecting). */
  next?: string;
};

export function errorState(error: unknown): FormState {
  return { error: error instanceof ApiError && error.status === 422 ? "invalid" : "generic" };
}
