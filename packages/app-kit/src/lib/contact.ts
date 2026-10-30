/** Links that open the phone's dialer or WhatsApp for a business's contact number. */

/**
 * The number in international form without the plus ("972501234567"), as WhatsApp wants it.
 * A number typed with a plus or 00 is taken as it is; a local number gets the country of the
 * business's currency (a leading 0 is dropped). Null when the country is not known.
 */
export function internationalDigits(phone: string, currency: string): string | null {
  const typed = phone.replace(/[^\d+]/g, "");
  if (typed.startsWith("+")) return typed.slice(1) || null;
  if (typed.startsWith("00")) return typed.slice(2) || null;
  const country = currency === "ILS" ? "972" : currency === "USD" ? "1" : null;
  if (!country) return null;
  return country + typed.replace(/^0+/, "");
}

/** A `tel:` link: the number as it was saved (the dialer understands local numbers). */
export function callHref(phone: string): string {
  return `tel:${phone.replace(/[^\d+]/g, "")}`;
}

/** A `https://wa.me/…` link, or null when the number's country cannot be told. */
export function whatsappHref(phone: string, currency: string): string | null {
  const digits = internationalDigits(phone, currency);
  return digits ? `https://wa.me/${digits}` : null;
}
