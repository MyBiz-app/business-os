import type { Metadata } from "next";
import { headers } from "next/headers";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages, getTranslations } from "next-intl/server";

import { PaletteScript } from "@/components/palette-script";
import { SkipLink } from "@/components/skip-link";
import { ThemeProvider } from "@/components/theme-provider";
import { localeDirection } from "@/i18n/config";
import { NONCE_HEADER } from "@/lib/csp";
import { mainFont } from "./fonts";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("app");
  return { title: t("name"), description: t("tagline") };
}

// Message namespaces that belong to the email templates and the Expo apps; no web screen reads
// them, so they are not worth sending to every browser.
const SERVER_ONLY_NAMESPACES = ["email", "client", "staffApp"];

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const locale = await getLocale();
  // Set by the proxy for the strict Content-Security-Policy (lib/csp.ts). The layout already
  // renders per request (the locale comes from a cookie), so reading it costs nothing.
  const nonce = (await headers()).get(NONCE_HEADER) ?? undefined;
  const messages = Object.fromEntries(
    Object.entries(await getMessages()).filter(([namespace]) => !SERVER_ONLY_NAMESPACES.includes(namespace)),
  );

  return (
    <html
      lang={locale}
      dir={localeDirection[locale]}
      className={`${mainFont.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <PaletteScript nonce={nonce} />
      </head>
      <body className="min-h-full flex flex-col">
        <ThemeProvider nonce={nonce}>
          <NextIntlClientProvider messages={messages}>
            <SkipLink />
            {children}
          </NextIntlClientProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
