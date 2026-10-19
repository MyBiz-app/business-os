"use server";

import type { components } from "@business-os/api-client";

import { apiFetch } from "@/lib/api";
import { getPlatform } from "@/lib/platform";

import type { ChatRole } from "./actions";

export type LibraryDocument = components["schemas"]["LibraryDocument"];
export type LibraryDocumentBody = components["schemas"]["LibraryDocumentBody"];
export type LibraryVersion = components["schemas"]["LibraryVersion"];
export type LibraryHit = components["schemas"]["LibrarySearchHit"];
export type LibraryChange = components["schemas"]["LibraryChange"];
export type RefreshReport = components["schemas"]["RefreshReport"];

export type LibraryResult<T> = { data?: T; error?: string };

const KNOWN = new Set(["forbidden", "body_required", "kind_cannot_change", "unsupported_file", "empty_file", "file_too_long", "unreadable_file", "file_too_large", "no_source", "not_found"]);

async function errorOf(response: Response): Promise<string> {
  const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  const detail = typeof body?.detail === "string" ? body.detail : "";
  return KNOWN.has(detail) ? detail : "generic";
}

/** The documents of one agent's library. */
export async function listLibrary(key: ChatRole): Promise<LibraryResult<LibraryDocument[]>> {
  const { api } = await getPlatform();
  const { data, response } = await api.GET("/platform/ai/agents/{key}/library", { params: { path: { key } } });
  return data ? { data } : { error: await errorOf(response) };
}

export async function openLibraryDocument(id: string): Promise<LibraryResult<LibraryDocumentBody>> {
  const { api } = await getPlatform();
  const { data, response } = await api.GET("/platform/ai/library/{doc_id}", { params: { path: { doc_id: id } } });
  return data ? { data } : { error: await errorOf(response) };
}

export async function libraryVersions(id: string): Promise<LibraryResult<LibraryVersion[]>> {
  const { api } = await getPlatform();
  const { data, response } = await api.GET("/platform/ai/library/{doc_id}/versions", { params: { path: { doc_id: id } } });
  return data ? { data } : { error: await errorOf(response) };
}

/** Adds a document (no id) or saves a change to one; a changed text becomes a new version. */
export async function saveLibraryDocument(key: ChatRole, id: string | null, change: LibraryChange): Promise<LibraryResult<LibraryDocumentBody>> {
  const { api } = await getPlatform();
  const { data, response } = id
    ? await api.PUT("/platform/ai/library/{doc_id}", { params: { path: { doc_id: id } }, body: change })
    : await api.POST("/platform/ai/agents/{key}/library", { params: { path: { key } }, body: change });
  return data ? { data } : { error: await errorOf(response) };
}

/** A file (text, Markdown, HTML, Word or PDF) read into the library. */
export async function uploadLibraryFile(key: ChatRole, formData: FormData): Promise<LibraryResult<LibraryDocumentBody>> {
  await getPlatform();
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) return { error: "empty_file" };
  const body = new FormData();
  for (const [name, value] of formData.entries()) if (value !== "") body.set(name, value);
  const response = await apiFetch(`/platform/ai/agents/${key}/library/upload`, { method: "POST", body }, "");
  return response.ok ? { data: (await response.json()) as LibraryDocumentBody } : { error: await errorOf(response) };
}

export async function setLibraryDocumentEnabled(id: string, enabled: boolean): Promise<LibraryResult<LibraryDocumentBody>> {
  const { api } = await getPlatform();
  const { data, response } = await api.PUT("/platform/ai/library/{doc_id}/enabled", { params: { path: { doc_id: id } }, body: { enabled } });
  return data ? { data } : { error: await errorOf(response) };
}

export async function deleteLibraryDocument(id: string): Promise<LibraryResult<true>> {
  const { api } = await getPlatform();
  const { response } = await api.DELETE("/platform/ai/library/{doc_id}", { params: { path: { doc_id: id } } });
  return response.ok ? { data: true } : { error: await errorOf(response) };
}

export async function restoreLibraryVersion(id: string, version: number): Promise<LibraryResult<LibraryDocumentBody>> {
  const { api } = await getPlatform();
  const { data, response } = await api.POST("/platform/ai/library/{doc_id}/restore", { params: { path: { doc_id: id } }, body: { version } });
  return data ? { data } : { error: await errorOf(response) };
}

/** Reads a few of the agent's sources (links) from the web; call again with a later offset until none remain. */
export async function refreshLibrarySources(key: ChatRole, offset: number): Promise<LibraryResult<RefreshReport>> {
  const { api } = await getPlatform();
  const { data, response } = await api.POST("/platform/ai/agents/{key}/library/refresh", { params: { path: { key }, query: { offset } } });
  return data ? { data } : { error: await errorOf(response) };
}

/** What the agent would find for a question. */
export async function searchLibrary(key: ChatRole, q: string): Promise<LibraryResult<LibraryHit[]>> {
  const { api } = await getPlatform();
  const { data, response } = await api.GET("/platform/ai/agents/{key}/library/search", { params: { path: { key }, query: { q } } });
  return data ? { data } : { error: await errorOf(response) };
}
