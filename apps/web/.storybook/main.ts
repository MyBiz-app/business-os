import type { StorybookConfig } from "@storybook/nextjs-vite";

// The live catalog of the product's components (docs/guides/design-system.md, "Storybook").
// Stories sit next to their component as *.stories.tsx.
const config: StorybookConfig = {
  stories: ["../src/**/*.stories.@(ts|tsx)"],
  addons: ["@storybook/addon-a11y"],
  framework: "@storybook/nextjs-vite",
  core: { disableTelemetry: true },
};

export default config;
