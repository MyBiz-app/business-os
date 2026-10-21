/** The address fields a form sent (see components/address-picker.tsx), as the API takes them.
 * `{}` when the person left the address alone (nothing chosen, nothing cleared), so a saved
 * address, including an older free-text one, is not wiped by saving something else. When the
 * person emptied a saved address, every part is null and the API clears it. */
export function addressFromForm(formData: FormData, prefix = "") {
  const text = (field: string) => String(formData.get(`${prefix}${field}`) ?? "").trim() || null;
  const code = (field: string) => {
    const raw = text(field);
    return raw === null ? null : Number(raw);
  };
  const cityCode = code("city_code");
  if (cityCode === null && text("address_clear") === null) return {};
  return {
    city_code: cityCode,
    street_code: code("street_code"),
    street_unlisted: text("street_unlisted"),
    house_number: text("house_number"),
    address_details: text("address_details"),
  };
}

/** Only the city of a form that asks for just that (where a client or lead is from): the number
 * when one was picked, `null` when a saved city was emptied, `{}` when it was left alone. */
export function cityFromForm(formData: FormData, prefix = ""): { city_code?: number | null } {
  const raw = String(formData.get(`${prefix}city_code`) ?? "").trim();
  if (raw) return { city_code: Number(raw) };
  return formData.get(`${prefix}address_clear`) ? { city_code: null } : {};
}
