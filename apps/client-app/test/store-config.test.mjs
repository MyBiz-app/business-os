import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const app = JSON.parse(read("../app.json")).expo;
const eas = JSON.parse(read("../eas.json"));
const plugin = (name) => app.plugins.find((p) => (Array.isArray(p) ? p[0] : p) === name);

test("iOS skips the export-compliance question (only standard HTTPS encryption)", () => {
  assert.equal(app.ios.infoPlist.ITSAppUsesNonExemptEncryption, false);
});

test("every permission the app declares has a plain explanation", () => {
  const picker = plugin("expo-image-picker")[1];
  assert.match(picker.photosPermission, /MyBiz/);
  assert.match(picker.cameraPermission, /MyBiz/);
  assert.match(plugin("expo-local-authentication")[1].faceIDPermission, /MyBiz/);
});

test("permissions the app does not need stay off", () => {
  assert.equal(plugin("expo-image-picker")[1].microphonePermission, false);
  assert.ok(app.android.blockedPermissions.includes("android.permission.RECORD_AUDIO"));
  const declared = JSON.stringify(app).toLowerCase();
  for (const word of ["location", "contacts", "calendar", "usertracking"]) assert.ok(!declared.includes(word), word);
});

test("the production build is a store bundle on its own update channel", () => {
  assert.equal(eas.build.production.android.buildType, "app-bundle");
  assert.equal(eas.build.production.channel, "production");
  assert.equal(eas.build.production.environment, "production");
  assert.deepEqual(eas.submit.production, {});
});

test("the store texts exist and the data-safety answers cover the sensitive staff data", () => {
  const safety = read("../../../docs/store/data-safety.md");
  for (const word of ["national ID", "Form 101", "payslips", "clock-in", "Delete my account", "rule 4.8"]) {
    assert.ok(safety.includes(word), word);
  }
  for (const file of ["listing.md", "review-notes.md", "screenshots.md"]) {
    assert.ok(read(`../../../docs/store/${file}`).length > 200, file);
  }
});

test("the Expo web build stays out of search results", () => {
  const vercel = JSON.parse(read("../vercel.json"));
  const rule = vercel.headers.find((h) => h.source === "/(.*)");
  assert.ok(rule.headers.some((h) => h.key === "X-Robots-Tag" && /noindex/.test(h.value)));
});
