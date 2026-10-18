"use server";

import type { components } from "@business-os/api-client";
import { revalidatePath } from "next/cache";

import type { FormState } from "@/lib/form-state";
import { getPlatformFor } from "@/lib/platform";

type Stage = components["schemas"]["WebsiteOrderUpdate"]["stage"];

/** Moves an order along the board and saves the address, the notes and the note to the business. */
export async function updateWebsiteOrder(orderId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api } = await getPlatformFor("businesses.act");
  const value = (name: string) => String(formData.get(name) ?? "");
  const { response } = await api.PATCH("/platform/website-orders/{order_id}", {
    params: { path: { order_id: orderId } },
    body: {
      stage: (value("stage") || null) as Stage,
      site_url: value("site_url"),
      notes: value("notes"),
      message: value("message") || null,
    },
  });
  if (!response.ok) {
    return { error: response.status === 422 ? "invalid" : "generic" };
  }
  revalidatePath("/platform/website-orders");
  return { saved: true };
}
