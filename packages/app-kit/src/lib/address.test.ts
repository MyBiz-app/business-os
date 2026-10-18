import assert from "node:assert/strict";
import { test } from "node:test";

import { addressBody, addressFromSaved, EMPTY_ADDRESS, isAddressComplete } from "./address.ts";

const chosen = { ...EMPTY_ADDRESS, cityCode: 5000, cityText: "תל אביב - יפו", streetCode: 404, streetText: "דיזנגוף", houseNumber: " 12 " };

test("an address needs a city, a street and a house number", () => {
  assert.equal(isAddressComplete(EMPTY_ADDRESS), false);
  assert.equal(isAddressComplete(chosen), true);
  assert.equal(isAddressComplete({ ...chosen, houseNumber: " " }), false);
  assert.equal(isAddressComplete({ ...chosen, cityCode: null }), false);
});

test("a street typed by hand counts when it is not on the list", () => {
  const typed = { ...chosen, streetCode: null, streetText: "", streetUnlisted: "רחוב חדש" };
  assert.equal(isAddressComplete(typed), true);
  assert.equal(addressBody(typed).street_unlisted, "רחוב חדש");
});

test("the body sends trimmed parts and nulls for empty ones", () => {
  assert.deepEqual(addressBody(chosen), {
    city_code: 5000,
    street_code: 404,
    street_unlisted: null,
    house_number: "12",
    address_details: null,
  });
});

test("a saved address loads back into the form", () => {
  const loaded = addressFromSaved({ city_code: 5000, city: "תל אביב - יפו", street_code: 404, street_name: "דיזנגוף", house_number: "12", address_details: "קומה 2" });
  assert.equal(loaded.cityText, "תל אביב - יפו");
  assert.equal(loaded.details, "קומה 2");
  // An older free-text address has no city code: the city text is not carried over as a choice.
  assert.equal(addressFromSaved({ city: "Haifa" }).cityText, "");
});
