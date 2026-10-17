"use server";

import { revalidatePath } from "next/cache";

import type { components } from "@business-os/api-client";

import { getTenant } from "@/lib/tenant";

export type RunError =
  | "run_blocked"
  | "warnings_open"
  | "forbidden"
  | "run_approved"
  | "run_exists"
  | "one_stage_at_a_time"
  | "cannot_acknowledge"
  | "period_in_future"
  | "nothing_to_correct"
  | "negative_net"
  | "run_not_approved"
  | "invalid"
  | "generic";
export type RunResult = { ok?: true; error?: RunError };
export type RunStage = "hours" | "additions" | "review" | "approved";

const KNOWN: RunError[] = ["run_blocked", "warnings_open", "run_approved", "run_exists", "one_stage_at_a_time", "cannot_acknowledge", "period_in_future", "nothing_to_correct", "negative_net", "run_not_approved"];

function failure(status: number, body: unknown): { error: RunError } {
  const detail = (body as { detail?: unknown } | null)?.detail;
  const known = KNOWN.find((code) => code === detail);
  if (known) return { error: known };
  if (status === 403) return { error: "forbidden" };
  return { error: status === 422 ? "invalid" : "generic" };
}

function done(): RunResult {
  revalidatePath("/team/payroll");
  return { ok: true };
}

export async function startRun(period: string): Promise<RunResult> {
  const { api, scope } = await getTenant();
  const response = await api.POST("/payroll/runs", { params: scope, body: { period } });
  if (!response.data) return failure(response.response.status, response.error);
  return done();
}

export async function refreshRun(period: string): Promise<RunResult> {
  const { api, scope } = await getTenant();
  const response = await api.POST("/payroll/runs/{period}/refresh", { params: { ...scope, path: { period } } });
  if (!response.data) return failure(response.response.status, response.error);
  return done();
}

export async function moveStage(period: string, stage: RunStage): Promise<RunResult> {
  const { api, scope } = await getTenant();
  const response = await api.POST("/payroll/runs/{period}/stage", { params: { ...scope, path: { period } }, body: { stage } });
  if (!response.data) return failure(response.response.status, response.error);
  return done();
}

/** Types in (or, with `null`, takes away) the amount of a component for this month. */
export async function typeAmount(period: string, userId: string, componentId: string, amountMinor: number | null): Promise<RunResult> {
  const { api, scope } = await getTenant();
  const response = await api.PUT("/payroll/runs/{period}/lines/{user_id}/typed", {
    params: { ...scope, path: { period, user_id: userId } },
    body: { component_id: componentId, amount_minor: amountMinor },
  });
  if (!response.data) return failure(response.response.status, response.error);
  return done();
}

export async function acknowledgeWarning(period: string, userId: string, key: string, acknowledged: boolean): Promise<RunResult> {
  const { api, scope } = await getTenant();
  const response = await api.POST("/payroll/runs/{period}/lines/{user_id}/acknowledge", {
    params: { ...scope, path: { period, user_id: userId } },
    body: { key, acknowledged },
  });
  if (!response.data) return failure(response.response.status, response.error);
  return done();
}

export async function markAccountantChecked(period: string): Promise<RunResult> {
  const { api, scope } = await getTenant();
  const response = await api.POST("/payroll/runs/{period}/accountant-check", { params: { ...scope, path: { period } } });
  if (!response.response.ok) return failure(response.response.status, response.error);
  return done();
}

export type Correction = components["schemas"]["Correction"];

export async function listCorrections(period: string, userId: string): Promise<Correction[]> {
  const { api, scope } = await getTenant();
  const response = await api.GET("/payroll/runs/{period}/payslips/{user_id}/corrections", { params: { ...scope, path: { period, user_id: userId } } });
  return response.data ?? [];
}

/** Issues a corrective payslip for an approved month (owner only; the API checks it). */
export async function issueCorrection(period: string, userId: string, reason: string, items: { label: string; amount_minor: number }[]): Promise<RunResult> {
  const { api, scope } = await getTenant();
  const response = await api.POST("/payroll/runs/{period}/payslips/{user_id}/corrections", {
    params: { ...scope, path: { period, user_id: userId } },
    body: { reason, items },
  });
  if (!response.data) return failure(response.response.status, response.error);
  return done();
}
