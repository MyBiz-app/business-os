const expo = require("eslint-config-expo/flat");
const { defineConfig } = require("eslint/config");

module.exports = defineConfig([
  expo,
  {
    ignores: ["dist/*", ".expo/*"],
  },
  {
    rules: {
      // These rules assume the React Compiler, which the apps don't use. Loading data in an
      // effect and keeping instance values in refs are the established patterns here.
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/purity": "warn",
    },
  },
]);
