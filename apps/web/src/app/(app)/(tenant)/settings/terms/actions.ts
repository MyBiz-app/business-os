"use server";

import { TERM_KEYS } from "@business-os/verticals";
import { getLocale } from "next-intl/server";
import { revalidatePath } from "next/cache";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { getTenant } from "@/lib/tenant";

/** Saves the words typed in the language of the page; the other language's words are kept as they
 * are, and an empty box goes back to the industry's word. */
export async function updateTerms(_state: FormState, formData: FormData): Promise<FormState> {
  const { tenant, api, scope } = await getTenant();
  const locale = await getLocale();
  const words: Record<string, string> = {};
  for (const key of TERM_KEYS) {
    const text = String(formData.get(key) ?? "").trim();
    if (text) words[key] = text;
  }
  try {
    unwrap(
      await api.PATCH("/tenants/current", {
        params: scope,
        body: { terms_override: { ...tenant.terms_override, [locale]: words } },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/", "layout");
  return { saved: true };
}
