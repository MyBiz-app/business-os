"use server";

import type { components } from "@business-os/api-client";
import { revalidatePath } from "next/cache";

import { ApiError, unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { getTenant } from "@/lib/tenant";

type Audience = components["schemas"]["CampaignCreate"]["audience"];
type Channel = components["schemas"]["Campaign"]["channel"];
type PhoneChannel = components["schemas"]["DirectMessage"]["channel"];

export type SendState = FormState & { sent?: number };
export type Reach = {
  recipients: number;
  byChannel: Record<string, number>;
  warnings: { variable: string; recipients: number }[];
};

/** The branches, channels and promotional flag of a message, as the form sends them. No branch
 * inputs means the whole network. */
function target(formData: FormData) {
  const channels = formData.getAll("channels").map(String) as Channel[];
  const locations = formData.getAll("location_ids").map(String);
  return {
    audience: String(formData.get("audience")) as Audience,
    channel: channels[0] ?? ("whatsapp" as Channel),
    channels: channels.length > 0 ? channels : (["whatsapp"] as Channel[]),
    location_ids: locations.length > 0 ? locations : null,
    subject: String(formData.get("subject") ?? "").trim() || null,
    promotional: formData.get("promotional") === "on",
  };
}

/** Who a message would reach right now (nothing is sent). */
export async function previewCampaign(input: {
  audience: string;
  channels: string[];
  locationIds: string[] | null;
  promotional: boolean;
  body?: string;
}): Promise<Reach> {
  const { api, scope } = await getTenant();
  try {
    const result = unwrap(
      await api.POST("/messages/campaigns", {
        params: scope,
        body: {
          audience: input.audience as Audience,
          channel: (input.channels[0] ?? "whatsapp") as Channel,
          channels: input.channels as Channel[],
          location_ids: input.locationIds && input.locationIds.length > 0 ? input.locationIds : null,
          promotional: input.promotional,
          body: input.body?.trim() || "-",
          dry_run: true,
        },
      }),
    );
    return { recipients: result.recipients, byChannel: result.by_channel ?? {}, warnings: result.warnings ?? [] };
  } catch {
    return { recipients: 0, byChannel: {}, warnings: [] };
  }
}

export async function sendCampaign(_state: SendState, formData: FormData): Promise<SendState> {
  const { api, scope } = await getTenant();
  try {
    const result = unwrap(
      await api.POST("/messages/campaigns", {
        params: scope,
        body: {
          ...target(formData),
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
          channel: (String(formData.get("channel") || "whatsapp")) as PhoneChannel,
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
