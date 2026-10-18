// The store ids live in one place: packages/brand/app-ids.json (they can never change after the first upload).
const ids = require("../../packages/brand/app-ids.json");

// Source maps reach Sentry (readable crash stack traces) only in a build that has an auth token;
// without SENTRY_AUTH_TOKEN the plugin is left out and nothing changes.
const sentryPlugins = process.env.SENTRY_AUTH_TOKEN
  ? [["@sentry/react-native/expo", { organization: process.env.SENTRY_ORG, project: process.env.SENTRY_PROJECT }]]
  : [];

module.exports = ({ config }) => ({
  ...config,
  ios: { ...config.ios, bundleIdentifier: ids.client },
  android: { ...config.android, package: ids.client },
  plugins: [...(config.plugins ?? []), ...sentryPlugins],
});
