import type { Decorator, Preview } from "@storybook/nextjs-vite";
import { type ReactNode, useEffect } from "react";

import "../src/app/globals.css";

// Every story is shown the way the product shows it: inside `.app-shell` (the Calm type scale and
// corners), on the page color, with the toolbar choosing light or dark and left-to-right or
// right-to-left. Compare the four combinations before a component is done.
function ProductFrame({ theme, direction, children }: { theme: string; direction: string; children: ReactNode }) {
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    root.dir = direction;
    root.lang = direction === "rtl" ? "he" : "en";
  }, [theme, direction]);
  return <div className="app-shell min-h-screen p-6">{children}</div>;
}

const withProduct: Decorator = (Story, context) => (
  <ProductFrame theme={String(context.globals.theme)} direction={String(context.globals.direction)}>
    <Story />
  </ProductFrame>
);

const preview: Preview = {
  decorators: [withProduct],
  globalTypes: {
    theme: {
      description: "Light or dark",
      toolbar: { title: "Theme", icon: "circlehollow", items: ["light", "dark"], dynamicTitle: true },
    },
    direction: {
      description: "Reading direction",
      toolbar: { title: "Direction", icon: "transfer", items: ["ltr", "rtl"], dynamicTitle: true },
    },
  },
  initialGlobals: { theme: "light", direction: "ltr" },
  parameters: { layout: "fullscreen", controls: { expanded: true } },
};

export default preview;
