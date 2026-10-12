"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";
import { localeDirection, matchLanguageTag, messages, type Locale } from "@business-os/i18n";

/** Last resort, when the root layout itself fails: it renders its own <html>, outside the
 * providers, so it reads the translations directly and picks the language from the saved
 * choice or the browser. Styles are inline because the stylesheet may not have loaded. */
function pickLocale(): Locale {
  if (typeof document === "undefined") return "he";
  const saved = /(?:^|; )NEXT_LOCALE=([^;]+)/.exec(document.cookie)?.[1];
  return matchLanguageTag(saved) ?? matchLanguageTag(navigator.language) ?? "he";
}

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  const locale = pickLocale();
  const t = messages[locale].errorPages;
  const retry = messages[locale].common.retry;

  return (
    <html lang={locale} dir={localeDirection[locale]}>
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "1rem",
          padding: "1rem",
          textAlign: "center",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <h1 style={{ fontSize: "1.5rem", margin: 0 }}>{t.title}</h1>
        <p style={{ maxWidth: "28rem", margin: 0 }}>{t.text}</p>
        {error.digest ? (
          <p dir="ltr" style={{ fontSize: "0.875rem", margin: 0 }}>
            {t.reference.replace("{code}", error.digest)}
          </p>
        ) : null}
        <button type="button" onClick={reset} style={{ padding: "0.5rem 1rem", fontSize: "1rem" }}>
          {retry}
        </button>
      </body>
    </html>
  );
}
