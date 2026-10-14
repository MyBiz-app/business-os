"use server";

import { revalidatePath } from "next/cache";

import { OTP_LENGTH, toE164 } from "@/lib/otp";
import { createClient } from "@/lib/supabase/server";

export type PhoneState = { error?: "invalid_phone" | "invalid_code" | "generic"; target?: string; done?: boolean };

/** Step one of verifying a mobile number for code sign-in: Supabase texts a code to it. */
export async function sendPhoneCode(_state: PhoneState, formData: FormData): Promise<PhoneState> {
  const phone = toE164(String(formData.get("phone") ?? ""));
  if (!phone) return { error: "invalid_phone" };
  const { error } = await (await createClient()).auth.updateUser({ phone });
  return error ? { error: "generic" } : { target: phone };
}

/** Step two: the code proves the number is theirs, and it can then be used to sign in. */
export async function verifyPhoneCode(_state: PhoneState, formData: FormData): Promise<PhoneState> {
  const target = String(formData.get("target") ?? "");
  const token = String(formData.get("code") ?? "").trim();
  if (!new RegExp(`^\\d{${OTP_LENGTH}}$`).test(token)) return { error: "invalid_code", target };
  const { error } = await (await createClient()).auth.verifyOtp({ phone: target, token, type: "phone_change" });
  if (error) return { error: "invalid_code", target };
  revalidatePath("/account");
  return { done: true };
}
