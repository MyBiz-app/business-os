import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { normalize, prefill } from "../app/(app)/(tenant)/website/brief/draft.ts";

describe("prefill", () => {
  it("fills empty answers from the business", () => {
    const draft = prefill(normalize(undefined), { locale: "he", address_city: "Haifa", website_url: "https://www.studio.co.il/home" });
    assert.deepEqual(draft.languages, ["he"]);
    assert.equal(draft.area, "Haifa");
    assert.equal(draft.domain, "have");
    assert.equal(draft.domain_name, "www.studio.co.il");
  });

  it("keeps what was already answered", () => {
    const draft = prefill(normalize({ languages: ["en"], area: "Tel Aviv", domain: "buy", no_logo: false, colors_from_brand: true, no_good_photos: false }), { locale: "he", address_city: "Haifa", website_url: "studio.co.il" });
    assert.deepEqual(draft.languages, ["en"]);
    assert.equal(draft.area, "Tel Aviv");
    assert.equal(draft.domain, "buy");
  });

  it("falls back to English and no domain", () => {
    const draft = prefill(normalize(undefined), { locale: "en" });
    assert.deepEqual(draft.languages, ["en"]);
    assert.equal(draft.domain, undefined);
  });
});
