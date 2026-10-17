"use server";

import { revalidatePath } from "next/cache";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { getTenantFor } from "@/lib/tenant";

/** Records (or withdraws) the client's agreement to marketing messages. */
export async function setMarketingConsent(clientId: string, consent: boolean, _state: FormState): Promise<FormState> {
  const { api, scope } = await getTenantFor("clients.write");
  try {
    unwrap(
      await api.PUT("/clients/{client_id}/marketing-consent", {
        params: { ...scope, path: { client_id: clientId } },
        body: { consent },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath(`/clients/${clientId}`);
  return { saved: true };
}
