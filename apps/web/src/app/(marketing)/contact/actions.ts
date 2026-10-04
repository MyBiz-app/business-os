"use server";

import { getLocale } from "next-intl/server";

import { API_URL } from "@/lib/api";

export type ContactState = { sent?: boolean; error?: "invalid" | "too_many_requests" | "generic" };

const text = (formData: FormData, name: string) => String(formData.get(name) ?? "").trim();

/** Sends the marketing contact form to the API (stored for the platform team). */
export async function sendContact(_state: ContactState, formData: FormData): Promise<ContactState> {
  const locale = (await getLocale()) === "en" ? "en" : "he";
  const response = await fetch(`${API_URL}/public/contact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: text(formData, "name"),
      email: text(formData, "email"),
      phone: text(formData, "phone") || null,
      business: text(formData, "business") || null,
      vertical: text(formData, "vertical") || null,
      message: text(formData, "message") || null,
      website: text(formData, "website") || null,
      locale,
    }),
  }).catch(() => null);
  if (response?.status === 202) return { sent: true };
  if (response?.status === 422) return { error: "invalid" };
  if (response?.status === 429) return { error: "too_many_requests" };
  return { error: "generic" };
}
