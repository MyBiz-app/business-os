"use server";

import { revalidatePath } from "next/cache";

import { getTenant } from "@/lib/tenant";

/** Closes the "website" card on the dashboard for good, for this person. */
export async function dismissWebsiteOffer(): Promise<void> {
  const { api } = await getTenant();
  await api.PUT("/me/tours/{key}", { params: { path: { key: "website_offer" } } });
  revalidatePath("/dashboard");
}
