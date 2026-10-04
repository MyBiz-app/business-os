"use server";

import type { components } from "@business-os/api-client";
import { revalidatePath } from "next/cache";

import { ApiError, unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { getTenant } from "@/lib/tenant";

type Audience = components["schemas"]["CampaignCreate"]["audience"];
type Channel = components["schemas"]["CampaignCreate"]["channel"];

export type SendState = FormState & { sent?: number };

export async function sendCampaign(_state: SendState, formData: FormData): Promise<SendState> {
  const { api, scope } = await getTenant();
  try {
    const result = unwrap(
      await api.POST("/messages/campaigns", {
        params: scope,
        body: {
          audience: String(formData.get("audience")) as Audience,
          channel: (String(formData.get("channel") || "whatsapp")) as Channel,
          body: String(formData.get("body") ?? ""),
          dry_run: false,
        },
      }),
    );
    revalidatePath("/messages");
    return { sent: result.recipients };
  } catch (error) {
    return errorState(error);
  }
}

export async function saveTemplate(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.POST("/messages/templates", {
        params: scope,
        body: { name: String(formData.get("name") ?? ""), body: String(formData.get("body") ?? "") },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/messages");
  return { saved: true };
}

export async function deleteTemplate(templateId: string): Promise<void> {
  const { api, scope } = await getTenant();
  const { response } = await api.DELETE("/messages/templates/{template_id}", {
    params: { ...scope, path: { template_id: templateId } },
  });
  if (!response.ok) throw new ApiError(response.status, "delete template failed");
  revalidatePath("/messages");
}

/** A message to one client or lead (from their page). */
export async function sendDirect(
  target: { client_id?: string; lead_id?: string },
  path: string,
  _state: FormState,
  formData: FormData,
): Promise<FormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.POST("/messages/direct", {
        params: scope,
        body: {
          ...target,
          channel: (String(formData.get("channel") || "whatsapp")) as Channel,
          body: String(formData.get("body") ?? ""),
        },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath(path);
  return { saved: true };
}
