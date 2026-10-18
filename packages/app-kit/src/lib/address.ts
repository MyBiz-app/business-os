/** An address being filled in with the official city and street lists (see components/address-picker). */
export type AddressValue = {
  cityCode: number | null;
  cityText: string;
  streetCode: number | null;
  streetText: string;
  /** A street that is not on the list, typed by hand (flagged for review). */
  streetUnlisted: string;
  houseNumber: string;
  details: string;
};

export const EMPTY_ADDRESS: AddressValue = {
  cityCode: null,
  cityText: "",
  streetCode: null,
  streetText: "",
  streetUnlisted: "",
  houseNumber: "",
  details: "",
};

/** A saved address, as the API returns it, loaded into the form. */
export function addressFromSaved(saved: {
  city_code?: number | null;
  city?: string | null;
  street_code?: number | null;
  street_name?: string | null;
  street_unlisted?: string | null;
  house_number?: string | null;
  address_details?: string | null;
}): AddressValue {
  return {
    cityCode: saved.city_code ?? null,
    cityText: saved.city_code ? (saved.city ?? "") : "",
    streetCode: saved.street_code ?? null,
    streetText: saved.street_name ?? "",
    streetUnlisted: saved.street_unlisted ?? "",
    houseNumber: saved.house_number ?? "",
    details: saved.address_details ?? "",
  };
}

/** City, a street (from the list or typed) and a house number are all there. */
export function isAddressComplete(value: AddressValue): boolean {
  return (
    value.cityCode !== null &&
    (value.streetCode !== null || value.streetUnlisted.trim() !== "") &&
    value.houseNumber.trim() !== ""
  );
}

/** The fields the API takes; empty parts are null. */
export function addressBody(value: AddressValue) {
  return {
    city_code: value.cityCode,
    street_code: value.streetCode,
    street_unlisted: value.streetCode === null ? value.streetUnlisted.trim() || null : null,
    house_number: value.houseNumber.trim() || null,
    address_details: value.details.trim() || null,
  };
}
