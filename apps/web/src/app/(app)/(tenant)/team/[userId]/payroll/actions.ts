"use server";

import { revalidatePath } from "next/cache";

import { ApiError } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

export type PayrollError =
  | "hourly_rate_required"
  | "monthly_amount_required"
  | "invalid_reference"
  | "form_exists"
  | "forbidden"
  | "invalid"
  | "generic";
export type PayrollResult<T = undefined> = { ok?: true; data?: T; error?: PayrollError };

const KNOWN: PayrollError[] = ["hourly_rate_required", "monthly_amount_required", "invalid_reference", "form_exists"];

function failure(status: number, body: unknown): { error: PayrollError } {
  const detail = (body as { detail?: unknown } | null)?.detail;
  const known = KNOWN.find((code) => code === detail);
  if (known) return { error: known };
  if (status === 403) return { error: "forbidden" };
  return { error: status === 422 ? "invalid" : "generic" };
}

export type EmploymentInput = {
  employment_type: "global" | "hourly" | "global_overtime";
  currency: string;
  monthly_amount_minor: number | null;
  hourly_rate_minor: number | null;
  scope_pct: number;
  start_date: string | null;
  work_days_per_week: number;
  job_title: string | null;
  pension: { fund_name: string | null; employee_pct: number; employer_pct: number; severance_pct: number } | null;
  employment_notice_date: string | null;
  bank: { bank_code: string; branch: string; account: string } | null;
};

export async function saveEmployment(userId: string, input: EmploymentInput): Promise<PayrollResult> {
  const { api, scope } = await getTenantFor("payroll.manage");
  const response = await api.PUT("/staff/{user_id}/employment", {
    params: { ...scope, path: { user_id: userId } },
    body: input,
  });
  if (!response.response.ok) return failure(response.response.status, response.error);
  revalidatePath(`/team/${userId}/payroll`);
  return { ok: true };
}

/** The full bank account, for someone with `identity.read`; the API logs every reveal. */
export async function revealBank(userId: string): Promise<PayrollResult<{ bank_code: string; branch: string; account: string }>> {
  const { api, scope } = await getTenantFor("payroll.read");
  const response = await api.POST("/staff/{user_id}/employment/bank/reveal", {
    params: { ...scope, path: { user_id: userId } },
  });
  if (!response.data) return failure(response.response.status, response.error);
  return { ok: true, data: response.data };
}

export async function requestForm101(userId: string, taxYear: number): Promise<PayrollResult> {
  const { api, scope } = await getTenantFor("payroll.manage");
  const response = await api.POST("/staff/{user_id}/form101", {
    params: { ...scope, path: { user_id: userId } },
    body: { tax_year: taxYear },
  });
  if (!response.response.ok) return failure(response.response.status, response.error);
  revalidatePath(`/team/${userId}/payroll`);
  return { ok: true };
}

export async function overrideCreditPoints(
  userId: string,
  taxYear: number,
  points: number | null,
  note: string,
): Promise<PayrollResult> {
  const { api, scope } = await getTenantFor("payroll.manage");
  const response = await api.PUT("/staff/{user_id}/form101/{tax_year}/credit-points", {
    params: { ...scope, path: { user_id: userId, tax_year: taxYear } },
    body: { points, note: note || null },
  });
  if (!response.response.ok) return failure(response.response.status, response.error);
  revalidatePath(`/team/${userId}/payroll`);
  return { ok: true };
}

export async function loadForm101(userId: string, taxYear: number) {
  const { api, scope } = await getTenantFor("payroll.read");
  const response = await api.GET("/staff/{user_id}/form101/{tax_year}", {
    params: { ...scope, path: { user_id: userId, tax_year: taxYear } },
  });
  if (!response.data) throw new ApiError(response.response.status, response.error);
  return response.data;
}
