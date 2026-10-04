// Country calling codes for local numbers ("050-..."), by the business's time zone.
const CALLING_CODES: Record<string, string> = {
  "Asia/Jerusalem": "972",
  "Europe/London": "44",
  "Europe/Paris": "33",
  "Europe/Berlin": "49",
  "Europe/Madrid": "34",
  "Europe/Rome": "39",
  "Europe/Amsterdam": "31",
};

/** International digits for wa.me, e.g. "050-123 4567" in Israel → "972501234567". */
export function internationalDigits(phone: string, timeZone: string): string | null {
  const trimmed = phone.trim();
  const digits = trimmed.replace(/\D/g, "");
  if (digits.length < 7) return null;
  if (trimmed.startsWith("+") || trimmed.startsWith("00")) return digits.replace(/^00/, "");
  const code = timeZone.startsWith("America/") ? "1" : CALLING_CODES[timeZone];
  if (digits.startsWith("0") && code) return code + digits.slice(1);
  return digits;
}

/** A link that opens WhatsApp (app or web) with a chat to the number, optionally pre-filled.
 * Free and works today: the message is sent from the user's own WhatsApp. */
export function whatsappLink(phone: string, timeZone: string, text?: string): string | null {
  const number = internationalDigits(phone, timeZone);
  if (!number) return null;
  return `https://wa.me/${number}${text ? `?text=${encodeURIComponent(text)}` : ""}`;
}
