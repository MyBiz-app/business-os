"use server";

import { revalidatePath } from "next/cache";

import { apiFetch } from "@/lib/api";

/** Closes the "website" card on the dashboard for good, for this person. The card is per person,
 * so this is a plain request for the signed-in person: closing a card never redirects anywhere,
 * and a failure just leaves the card for one more visit. */
export async function dismissWebsiteOffer(): Promise<void> {
  try {
    await apiFetch("/me/tours/website_offer", { method: "PUT" }, "");
  } catch {
    return;
  }
  revalidatePath("/dashboard");
}
