// The store ids live in one place: packages/brand/app-ids.json (they can never change after the first upload).
const ids = require("../../packages/brand/app-ids.json");

module.exports = ({ config }) => ({
  ...config,
  ios: { ...config.ios, bundleIdentifier: ids.client },
  android: { ...config.android, package: ids.client },
});
