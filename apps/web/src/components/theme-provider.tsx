"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";

// next-themes renders an inline script that sets the theme before the first paint. It runs from
// the server HTML; if React ever re-creates it in the browser (for example after a hydration
// mismatch caused by a browser extension), React warns about script tags. On the client the
// script is marked as a data block, which React accepts and nothing executes twice.
const scriptProps = { type: typeof window === "undefined" ? "text/javascript" : "application/json" };

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange scriptProps={scriptProps}>
      {children}
    </NextThemesProvider>
  );
}
