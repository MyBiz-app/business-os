"use server";

import { API_URL } from "@/lib/api";

export type InquiryState = { sent?: boolean; error?: "invalid" | "contact" | "too_many_requests" | "generic" };

const text = (formData: FormData, name: string) => String(formData.get(name) ?? "").trim() || null;

/** Sends a business's public inquiry form to the API; it becomes a new lead. */
export async function sendInquiry(code: string, _state: InquiryState, formData: FormData): Promise<InquiryState> {
  if (!text(formData, "email") && !text(formData, "phone")) return { error: "contact" };
  const response = await fetch(`${API_URL}/public/businesses/${encodeURIComponent(code)}/inquiries`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      first_name: text(formData, "first_name"),
      last_name: text(formData, "last_name"),
      email: text(formData, "email"),
      phone: text(formData, "phone"),
      interest: text(formData, "interest"),
      website: text(formData, "website"),
    }),
  }).catch(() => null);
  if (response?.status === 202) return { sent: true };
  if (response?.status === 422) return { error: "invalid" };
  if (response?.status === 429) return { error: "too_many_requests" };
  return { error: "generic" };
}
