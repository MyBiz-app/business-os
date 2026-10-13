import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

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
  // Right-to-left safety: no physical left/right classes (see eslint-rules/no-physical-classes.mjs).
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["**/*.test.ts"],
    plugins: { direction },
    rules: { "direction/no-physical-classes": "error" },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
