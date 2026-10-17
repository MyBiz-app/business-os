"use server";

import type { components } from "@business-os/api-client";
import { revalidatePath } from "next/cache";

import { apiFetch, ApiError, unwrap } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

export type MoveSession = components["schemas"]["MigrationSessionOut"];
export type MoveFile = components["schemas"]["MigrationFileOut"];
export type MoveReport = components["schemas"]["MoveReport"];
export type UndoReport = components["schemas"]["MigrationUndoReport"];
export type MoveKind = NonNullable<MoveFile["kind"]>;

export type MoveResult<T> = { data?: T; error?: string };

const PERMISSION = "migration.manage";

/** The API's reason (`detail`) when it gave one, so the page can say what went wrong. */
function failure(error: unknown): { error: string } {
  const detail = error instanceof ApiError ? (error.body as { detail?: unknown } | null)?.detail : undefined;
  return { error: typeof detail === "string" ? detail : "generic" };
}

async function call<T>(work: () => Promise<T>): Promise<MoveResult<T>> {
  try {
    const data = await work();
    revalidatePath("/migration");
    return { data };
  } catch (error) {
    return failure(error);
  }
}

export async function startMove(origin: string): Promise<MoveResult<MoveSession>> {
  const { api, scope } = await getTenantFor(PERMISSION);
  return call(async () =>
    unwrap(await api.POST("/migration/sessions", { params: scope, body: { origin, rights_confirmed: true } })),
  );
}

export async function uploadMoveFile(sessionId: string, formData: FormData): Promise<MoveResult<MoveFile>> {
  const { tenant } = await getTenantFor(PERMISSION);
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) return { error: "empty_file" };
  const body = new FormData();
  body.set("file", file);
  const response = await apiFetch(`/migration/sessions/${sessionId}/files`, { method: "POST", body }, tenant.id);
  if (!response.ok) {
    const detail = ((await response.json().catch(() => null)) as { detail?: unknown } | null)?.detail;
    return { error: typeof detail === "string" ? detail : "generic" };
  }
  revalidatePath("/migration");
  return { data: (await response.json()) as MoveFile };
}

export async function updateMoveFile(
  sessionId: string,
  fileId: string,
  change: { kind?: MoveKind; mapping?: (string | null)[] },
): Promise<MoveResult<MoveFile>> {
  const { api, scope } = await getTenantFor(PERMISSION);
  return call(async () =>
    unwrap(
      await api.PUT("/migration/sessions/{session_id}/files/{file_id}", {
        params: { ...scope, path: { session_id: sessionId, file_id: fileId } },
        body: change,
      }),
    ),
  );
}

export async function removeMoveFile(sessionId: string, fileId: string): Promise<MoveResult<true>> {
  const { api, scope } = await getTenantFor(PERMISSION);
  return call(async () => {
    const result = await api.DELETE("/migration/sessions/{session_id}/files/{file_id}", {
      params: { ...scope, path: { session_id: sessionId, file_id: fileId } },
    });
    if (!result.response.ok) throw new ApiError(result.response.status, result.error);
    return true as const;
  });
}

/** The dry run (`commit` false) or the import itself. */
export async function runMove(sessionId: string, commit: boolean): Promise<MoveResult<MoveReport>> {
  const { api, scope } = await getTenantFor(PERMISSION);
  const path = { params: { ...scope, path: { session_id: sessionId } } };
  return call(async () => {
    const result = commit
      ? await api.POST("/migration/sessions/{session_id}/import", path)
      : await api.POST("/migration/sessions/{session_id}/preview", path);
    if (commit && result.data) {
      revalidatePath("/clients");
      revalidatePath("/services");
      revalidatePath("/team");
    }
    return unwrap(result);
  });
}

export async function undoBatch(batchId: string, includeEdited: boolean, commit: boolean): Promise<MoveResult<UndoReport>> {
  const { api, scope } = await getTenantFor(PERMISSION);
  const options = { params: { ...scope, path: { batch_id: batchId } }, body: { include_edited: includeEdited } };
  return call(async () =>
    unwrap(
      commit
        ? await api.POST("/migration/batches/{batch_id}/undo", options)
        : await api.POST("/migration/batches/{batch_id}/undo-preview", options),
    ),
  );
}
