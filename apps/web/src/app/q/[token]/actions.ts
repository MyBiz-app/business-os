"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { getApi } from "@/lib/api";

export type AnswerState = { error?: "name_required" | "expired" | "already_answered" | "generic" };

/** Accepts (with a name) or declines the quote from its private link. */
export async function answerQuote(token: string, accept: boolean, _state: AnswerState, formData: FormData): Promise<AnswerState> {
  const { error, response } = await (await getApi()).POST("/public/quotes/{token}/answer", {
    params: { path: { token } },
    body: { accept, name: accept ? String(formData.get("name") ?? "") : null },
  });
  if (!response.ok) {
    const detail = (error as { detail?: unknown } | undefined)?.detail;
    return { error: detail === "name_required" || detail === "expired" || detail === "already_answered" ? detail : "generic" };
  }
  revalidatePath(`/q/${token}`);
  return {};
}

/** Pays the deposit: simulated payments record it now; a real provider sends the client to its
 * own payment page. */
export async function payDeposit(token: string, key: string): Promise<void> {
  const { data } = await (await getApi()).POST("/public/quotes/{token}/deposit", {
    params: { path: { token } },
    body: { idempotency_key: key },
  });
  if (data?.pay_url) redirect(data.pay_url);
  revalidatePath(`/q/${token}`);
}
