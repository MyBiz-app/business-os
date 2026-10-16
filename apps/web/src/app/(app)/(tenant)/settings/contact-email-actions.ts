"use server";

import { revalidatePath } from "next/cache";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { getTenantFor } from "@/lib/tenant";

export type ContactEmailState = FormState & { sent?: boolean | null };
type Purpose = "main" | "inbox" | "billing" | "reply_to" | "notifications";

const refresh = () => {
  revalidatePath("/settings");
  revalidatePath("/locations/[id]", "page");
};

/** Sets one address of the business (no branch) or of a branch; it waits for confirmation. */
export async function saveContactEmail(
  locationId: string | null,
  purpose: Purpose,
  _state: ContactEmailState,
  formData: FormData,
): Promise<ContactEmailState> {
  const { api, scope } = await getTenantFor("business.settings");
  const params = { ...scope, path: { purpose }, query: { location_id: locationId ?? undefined } };
  const email = String(formData.get("email") ?? "").trim();
  try {
    if (email === "") {
      unwrap(await api.DELETE("/contact-emails/{purpose}", { params }));
      refresh();
      return { saved: true };
    }
    const result = unwrap(await api.PUT("/contact-emails/{purpose}", { params, body: { email } }));
    refresh();
    return { saved: true, sent: result.email_sent ?? null };
  } catch (error) {
    return errorState(error);
  }
}

export async function resendContactEmail(
  locationId: string | null,
  purpose: Purpose,
  _state: ContactEmailState,
): Promise<ContactEmailState> {
  const { api, scope } = await getTenantFor("business.settings");
  try {
    const result = unwrap(
      await api.POST("/contact-emails/{purpose}/resend", {
        params: { ...scope, path: { purpose }, query: { location_id: locationId ?? undefined } },
      }),
    );
    return { saved: true, sent: result.email_sent ?? null };
  } catch (error) {
    return errorState(error);
  }
}
