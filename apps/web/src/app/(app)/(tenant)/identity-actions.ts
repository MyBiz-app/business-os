"use server";

import { revalidatePath } from "next/cache";

import { ApiError } from "@/lib/api";
import { getTenant } from "@/lib/tenant";

export type IdentitySubject = { kind: "member" | "client"; id: string };

export type IdentityView = {
  present: boolean;
  id_type?: "il_id" | "passport" | "foreign" | null;
  country?: string | null;
  last4?: string | null;
  can_reveal: boolean;
  /** Clients only: off, optional or required (whether the business asks). */
  mode?: string;
};

export type IdentityError =
  | "invalid_id_number"
  | "invalid_id_country"
  | "id_number_in_use"
  | "client_id_off"
  | "forbidden"
  | "generic";

export type IdentityResult = { identity?: IdentityView; number?: string; error?: IdentityError };

const KNOWN: IdentityError[] = ["invalid_id_number", "invalid_id_country", "id_number_in_use", "client_id_off", "forbidden"];

function failure(error: unknown): IdentityResult {
  if (error instanceof ApiError) {
    const detail = (error.body as { detail?: unknown } | null)?.detail;
    const known = KNOWN.find((code) => code === detail);
    if (known) return { error: known };
    if (error.status === 403) return { error: "forbidden" };
  }
  return { error: "generic" };
}

async function pathParams(subject: IdentitySubject) {
  const { api, scope } = await getTenant();
  return { api, scope, id: subject.id };
}

/** What the screen may show of someone's ID number: never the number itself. */
export async function loadIdentity(subject: IdentitySubject): Promise<IdentityResult> {
  const { api, scope, id } = await pathParams(subject);
  const response =
    subject.kind === "member"
      ? await api.GET("/staff/{user_id}/identity", { params: { ...scope, path: { user_id: id } } })
      : await api.GET("/clients/{client_id}/identity", { params: { ...scope, path: { client_id: id } } });
  return response.data ? { identity: response.data } : failure(new ApiError(response.response.status, response.error));
}

export async function saveIdentity(
  subject: IdentitySubject,
  body: { id_type: "il_id" | "passport" | "foreign"; number: string; country?: string },
): Promise<IdentityResult> {
  const { api, scope, id } = await pathParams(subject);
  const payload = { ...body, country: body.id_type === "il_id" ? null : (body.country ?? null) };
  const response =
    subject.kind === "member"
      ? await api.PUT("/staff/{user_id}/identity", { params: { ...scope, path: { user_id: id } }, body: payload })
      : await api.PUT("/clients/{client_id}/identity", { params: { ...scope, path: { client_id: id } }, body: payload });
  if (!response.data) return failure(new ApiError(response.response.status, response.error));
  revalidatePath(subject.kind === "client" ? `/clients/${id}` : "/team");
  return { identity: response.data };
}

export async function removeIdentity(subject: IdentitySubject): Promise<IdentityResult> {
  const { api, scope, id } = await pathParams(subject);
  const response =
    subject.kind === "member"
      ? await api.DELETE("/staff/{user_id}/identity", { params: { ...scope, path: { user_id: id } } })
      : await api.DELETE("/clients/{client_id}/identity", { params: { ...scope, path: { client_id: id } } });
  if (response.response.status >= 400) return failure(new ApiError(response.response.status, response.error));
  revalidatePath(subject.kind === "client" ? `/clients/${id}` : "/team");
  return { identity: { present: false, can_reveal: false } };
}

/** The full number, for someone with `identity.read`. The API writes every reveal to the audit log. */
export async function revealIdentity(subject: IdentitySubject): Promise<IdentityResult> {
  const { api, scope, id } = await pathParams(subject);
  const response =
    subject.kind === "member"
      ? await api.POST("/staff/{user_id}/identity/reveal", { params: { ...scope, path: { user_id: id } } })
      : await api.POST("/clients/{client_id}/identity/reveal", { params: { ...scope, path: { client_id: id } } });
  return response.data ? { number: response.data.number } : failure(new ApiError(response.response.status, response.error));
}
