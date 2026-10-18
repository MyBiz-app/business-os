"use server";

import { redirect } from "next/navigation";

import { getApi, unwrap } from "@/lib/api";

const field = (form: FormData, name: string) => String(form.get(name) ?? "");

/** The person lets the AI app read the business they picked (and, if they ticked it, suggest
 * changes that wait for their approval): the API makes a one-time code and
 * says where to send the browser back to (the app's own address, which it checked). */
export async function approveConnection(form: FormData): Promise<void> {
  const { redirect_to } = unwrap(
    await (await getApi()).POST("/mcp-oauth/approve", {
      params: { header: { "X-Tenant-Id": field(form, "tenant_id") } },
      body: {
        client_id: field(form, "client_id"),
        redirect_uri: field(form, "redirect_uri"),
        code_challenge: field(form, "code_challenge"),
        state: field(form, "state"),
        propose: form.get("propose") === "on",
      },
    }),
  );
  redirect(redirect_to);
}

/** Says no: back to the app with `access_denied`. The address is only used if the API knows it as
 * one this app registered, so this can't send anyone to a place of their choosing. */
export async function denyConnection(form: FormData): Promise<void> {
  const clientId = field(form, "client_id");
  const redirectUri = field(form, "redirect_uri");
  unwrap(
    await (await getApi()).GET("/mcp-oauth/clients/{client_id}", {
      params: { path: { client_id: clientId }, query: { redirect_uri: redirectUri } },
    }),
  );
  const back = new URL(redirectUri);
  back.searchParams.set("error", "access_denied");
  const state = field(form, "state");
  if (state) back.searchParams.set("state", state);
  redirect(back.toString());
}
