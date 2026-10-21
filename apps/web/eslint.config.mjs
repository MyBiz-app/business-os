import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

import designSystem from "./eslint-rules/design-system.mjs";
import direction from "./eslint-rules/no-physical-classes.mjs";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // Server actions used with useActionState receive a state argument they may not need.
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    },
  },
  // Code order: big files and hard-coded UI text are warnings, not errors (go-live GL25). New code
  // should stay under the limit; user-facing text comes from the translation files.
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["**/*.test.ts"],
    rules: {
      "max-lines": ["warn", { max: 500, skipBlankLines: true, skipComments: true }],
    },
  },
  {
    files: ["src/**/*.tsx"],
    rules: { "react/jsx-no-literals": ["warn", { noStrings: false, allowedStrings: ["/", "-", "·", "•", ":"] }] },
  },
  // Right-to-left safety: no physical left/right classes (see eslint-rules/no-physical-classes.mjs).
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["**/*.test.ts"],
    plugins: { direction },
    rules: { "direction/no-physical-classes": "error" },
  },
  // Design system: tokens-only colors and system buttons (eslint-rules/design-system.mjs).
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["**/*.test.ts"],
    plugins: { "design-system": designSystem },
    rules: { "design-system/no-raw-colors": "error", "design-system/no-raw-button": "error", "design-system/no-scroll-jump": "error", "design-system/no-handrolled-ui": "error" },
  },
  // Stories show text literally; they are examples, not product screens.
  {
    files: ["src/**/*.stories.tsx"],
    rules: { "react/jsx-no-literals": "off" },
  },
  // R4 (dashboard and reports) fixes its own period links; drop this block when it lands.
  {
    files: ["src/app/(app)/(tenant)/dashboard/**", "src/app/(app)/(tenant)/reports/**"],
    rules: { "design-system/no-scroll-jump": "off" },
  },
  // The allow-list for raw colors: the token source, brand marks and illustrations, where a color
  // is the content itself (a logo, a palette swatch, a mock-up of the product). Everything else
  // uses tokens. Keep this list short; add a file only with a reason here.
  {
    files: [
      "src/lib/brand.ts", // derives AA-safe brand colors (math on hex)
      "src/lib/palette-colors.ts", // the palette swatches people choose from
      "src/lib/brand-presets.ts", // the ready-made brand colors in Settings → Branding
      "src/lib/calendar.ts", // event colors people choose from
      "src/components/palette.tsx", // the palette picker
      "src/components/modules/module-icon.tsx", // one illustrated icon per module
      "src/components/auth/provider-marks.tsx", // Google/Apple logos
      "src/components/marketing/mocks.tsx", // product mock-ups on the marketing site
      "src/components/marketing/demo-stage.tsx", // the hero's animated product stage
      "src/app/(marketing)/page.tsx", // hero gradient on the always-dark band
      "src/app/(marketing)/start/journey-pieces.tsx", // signup journey illustrations
      "src/app/(marketing)/opengraph-image.tsx", // rendered image, no CSS variables
      "src/app/global-error.tsx", // renders outside the app's CSS
      "src/app/(app)/(tenant)/messages/composer.tsx", // the editor's color swatches
      "src/lib/agent-templates.ts", // each AI agent's signature color
      "src/app/(app)/(tenant)/ai/agent-wizard.tsx", // team/agent color choices
      "src/app/(app)/(tenant)/ai/structure-panel.tsx", // team color swatches
      "src/app/(app)/(tenant)/ai/team-map.tsx", // white label on a team's own color
      "src/app/(app)/(tenant)/content/network-icon.tsx", // social network brand marks
      "src/app/(app)/(tenant)/content/line-chart.tsx", // one color per social network series
      "src/components/marketing/day-clock.tsx", // the dial's sky colors through the day
      "src/components/marketing/home-phone-stage.tsx", // the hero phone mock-up
      "src/components/modules/offer-picture.tsx", // WhatsApp / SMS look-alike mock-ups
    ],
    rules: { "design-system/no-raw-colors": "off" },
  },
  // global-error.tsx renders without the app's CSS, so its one button is styled inline.
  {
    files: ["src/app/global-error.tsx"],
    rules: { "design-system/no-raw-button": "off" },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    "storybook-static/**",
  ]),
]);

export default eslintConfig;
