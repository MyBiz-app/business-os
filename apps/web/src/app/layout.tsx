import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getTranslations } from "next-intl/server";

import { clientMessages } from "@/components/scoped-messages";
import { PaletteScript } from "@/components/palette-script";
import { ThemeProvider } from "@/components/theme-provider";
import { localeDirection } from "@/i18n/config";
import { mainFont } from "./fonts";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("app");
  return { title: t("name"), description: t("tagline") };
}

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const locale = await getLocale();
  const messages = await clientMessages([]);

  return (
    <html
      lang={locale}
      dir={localeDirection[locale]}
      className={`${mainFont.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <PaletteScript />
      </head>
      <body className="min-h-full flex flex-col">
        <ThemeProvider>
          <NextIntlClientProvider messages={messages}>{children}</NextIntlClientProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
