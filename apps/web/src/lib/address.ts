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
