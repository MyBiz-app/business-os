const expo = require("eslint-config-expo/flat");
const { defineConfig } = require("eslint/config");

module.exports = defineConfig([
  expo,
  {
    ignores: ["dist/*", ".expo/*"],
  },
  {
    // Design system: colors come from the palette (@business-os/design-tokens, app-kit lib/theme.ts)
    // or `fixedColors`; a hex literal anywhere else is an error.
    files: ["**/*.{ts,tsx}"],
    ignores: ["**/*.test.*", "**/lib/theme.ts", "**/lib/brand.ts", "**/launch-splash.tsx", "**/brand-color-card.tsx"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "Literal[value=/^#[0-9a-fA-F]{3,8}$/]",
          message: "A hex color. Use the palette (useTheme().palette) or fixedColors from lib/theme.ts.",
        },
      ],
    },
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
