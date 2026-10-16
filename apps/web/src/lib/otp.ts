/** One-time sign-in codes: how long they are, how people choose where to get one, and how a
 * phone number is written for Supabase (E.164). Pure, so it can be tested. */

/** Must equal `[auth.email] otp_length` in supabase/config.toml (and the hosted project). */
export const OTP_LENGTH = 6;

export type OtpChannel = "email" | "sms" | "whatsapp";

/** What the Supabase project allows (`/auth/v1/settings`) plus the WhatsApp switch. Email is
 * always available; a phone code needs a configured SMS provider; WhatsApp also needs the flag. */
export function availableChannels(settings: { external?: Record<string, boolean> } | null, whatsappFlag: boolean): OtpChannel[] {
  const channels: OtpChannel[] = ["email"];
  if (settings?.external?.phone) {
    channels.push("sms");
    if (whatsappFlag) channels.push("whatsapp");
  }
  return channels;
}

/** E.164 for Supabase. A local Israeli number (0501234567) becomes +972501234567; a number that
 * already starts with + or 00 is kept. Returns null when it cannot be a phone number. */
export function toE164(input: string, defaultCountryCode = "972"): string | null {
  const raw = input.trim();
  let digits = raw.replace(/\D/g, "");
  if (!digits) return null;
  if (raw.startsWith("+")) {
    // already international
  } else if (digits.startsWith("00")) {
    digits = digits.slice(2);
  } else if (digits.startsWith("0")) {
    digits = defaultCountryCode + digits.slice(1);
  } else {
    return null;
  }
  return digits.length >= 8 && digits.length <= 15 ? `+${digits}` : null;
}
