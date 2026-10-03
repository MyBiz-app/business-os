import { cookies, headers } from "next/headers";
import { getRequestConfig } from "next-intl/server";

import { messages } from "@business-os/i18n";

import { defaultLocale, isLocale, LOCALE_COOKIE, matchAcceptLanguage } from "./config";

// Locale comes from the user's choice (cookie), then the browser, then the default.
// URLs are not locale-prefixed: this is an app, not a marketing site.
export default getRequestConfig(async () => {
  const cookieLocale = (await cookies()).get(LOCALE_COOKIE)?.value;
  const locale = isLocale(cookieLocale)
    ? cookieLocale
    : (matchAcceptLanguage((await headers()).get("accept-language")) ?? defaultLocale);

  return {
    locale,
    messages: messages[locale],
  };
});
