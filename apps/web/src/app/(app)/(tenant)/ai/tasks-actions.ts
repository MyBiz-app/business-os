"use server";

import { revalidatePath } from "next/cache";

import type { components } from "@business-os/api-client";

import { ApiError, unwrap } from "@/lib/api";
import { getTenant } from "@/lib/tenant";

export type TaskBoard = components["schemas"]["Tasks"];
export type TaskCard = components["schemas"]["TaskCard"];
export type TaskRun = components["schemas"]["RunCard"];
export type TaskChange = components["schemas"]["TaskUpdate"];

export type TaskResult = { ok: true } | { ok: false; error: "time_passed" | "invalid" | "generic" };

function failure(error: unknown): TaskResult {
  const detail = error instanceof ApiError ? (error.body as { detail?: unknown } | null)?.detail : null;
  if (detail === "time_passed") return { ok: false, error: "time_passed" };
  return { ok: false, error: error instanceof ApiError && error.status === 422 ? "invalid" : "generic" };
}

/** Pause or resume a task, change its name, instruction or time. */
export async function updateTask(id: string, change: TaskChange): Promise<TaskResult> {
  const { api, scope } = await getTenant();
  try {
    unwrap(await api.PATCH("/ai/tasks/{task_id}", { params: { ...scope, path: { task_id: id } }, body: change }));
  } catch (error) {
    return failure(error);
  }
  revalidatePath("/ai");
  return { ok: true };
}

export async function deleteTask(id: string): Promise<TaskResult> {
  const { api, scope } = await getTenant();
  const { response } = await api.DELETE("/ai/tasks/{task_id}", { params: { ...scope, path: { task_id: id } } });
  if (!response.ok) return { ok: false, error: "generic" };
  revalidatePath("/ai");
  return { ok: true };
}

/** Runs the task now, as its owner; the schedule stays as it was. */
export async function runTaskNow(id: string): Promise<TaskResult> {
  const { api, scope } = await getTenant();
  try {
    unwrap(await api.POST("/ai/tasks/{task_id}/run", { params: { ...scope, path: { task_id: id } } }));
  } catch (error) {
    return failure(error);
  }
  revalidatePath("/ai");
  return { ok: true };
}

export async function taskRuns(id: string): Promise<TaskRun[]> {
  const { api, scope } = await getTenant();
  const { data } = await api.GET("/ai/tasks/{task_id}/runs", { params: { ...scope, path: { task_id: id } } });
  return data ?? [];
}
