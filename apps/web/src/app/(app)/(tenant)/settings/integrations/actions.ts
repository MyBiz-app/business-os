"use server";

import { revalidatePath } from "next/cache";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { getTenant } from "@/lib/tenant";

type Capability = "payments" | "invoicing" | "messaging";

/** Connects (or switches to) a provider: inputs named `setting.<key>`; an empty secret keeps
 * the one already set. */
export async function connectProvider(capability: Capability, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  const settings: Record<string, string> = {};
  for (const [name, value] of formData.entries()) {
    if (name.startsWith("setting.")) settings[name.slice("setting.".length)] = String(value);
  }
  try {
    unwrap(
      await api.PUT("/integrations/{capability}", {
        params: { ...scope, path: { capability } },
        body: { provider: String(formData.get("provider") ?? ""), settings },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/settings/integrations");
  return { saved: true };
}

export async function disconnectProvider(capability: Capability): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(await api.DELETE("/integrations/{capability}", { params: { ...scope, path: { capability } } }));
  revalidatePath("/settings/integrations");
}
