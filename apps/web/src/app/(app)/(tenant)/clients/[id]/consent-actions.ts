"use server";

import { revalidatePath } from "next/cache";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { getTenantFor } from "@/lib/tenant";

const DESK_SOURCES = ["desk_signed", "desk_verbal", "desk_other"] as const;
type DeskSource = (typeof DESK_SOURCES)[number];

/** Records (or withdraws) the client's agreement to marketing messages. An agreement needs the
 * way the client gave it. */
export async function setMarketingConsent(clientId: string, consent: boolean, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenantFor("clients.write");
  const picked = String(formData.get("source") ?? "");
  const source = DESK_SOURCES.find((s): s is DeskSource => s === picked);
  if (consent && !source) return { error: "invalid" };
  try {
    unwrap(
      await api.PUT("/clients/{client_id}/marketing-consent", {
        params: { ...scope, path: { client_id: clientId } },
        body: { consent, source },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath(`/clients/${clientId}`);
  return { saved: true };
}
