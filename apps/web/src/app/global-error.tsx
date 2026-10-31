"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";
import { localeDirection, matchLanguageTag, type Locale } from "@business-os/i18n/locales";

import { ERROR_MESSAGES } from "@/lib/error-messages";

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
  const t = ERROR_MESSAGES[locale];
  const retry = t.retry;

  return (
    <html lang={locale} dir={localeDirection[locale]}>
      <head>
        {/* The root layout (and its tokens) failed to load, so this page carries its own light/dark palette. */}
        <style>{`:root{--bg:#f7f7f8;--fg:#18181b;--accent:#2563eb}@media (prefers-color-scheme:dark){:root{--bg:#111113;--fg:#f4f4f5;--accent:#2563eb}}`}</style>
      </head>
      <body
        style={{
          background: "var(--bg)",
          color: "var(--fg)",
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "1rem",
          padding: "1rem",
          textAlign: "center",
          fontFamily: "Assistant, system-ui, sans-serif",
        }}
      >
        <h1 style={{ fontSize: "1.5rem", margin: 0 }}>{t.title}</h1>
        <p style={{ maxWidth: "28rem", margin: 0 }}>{t.text}</p>
        {error.digest ? (
          <p dir="ltr" style={{ fontSize: "0.875rem", margin: 0 }}>
            {t.reference.replace("{code}", error.digest)}
          </p>
        ) : null}
        <button type="button" onClick={reset} style={{ padding: "0.625rem 1.5rem", fontSize: "1rem", fontWeight: 600, color: "#fff", background: "var(--accent)", border: 0, borderRadius: "999px", cursor: "pointer" }}>
          {retry}
        </button>
        {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
        <a href="/" style={{ padding: "0.625rem 1.5rem", fontSize: "1rem", fontWeight: 600, color: "var(--fg)", background: "transparent", border: "1px solid currentColor", borderRadius: "999px", cursor: "pointer", textDecoration: "none" }}>
          {t.toSite}
        </a>
        <form action="/escape/sign-out" method="post" style={{ margin: 0 }}>
          <button type="submit" style={{ padding: "0.625rem 1.5rem", fontSize: "1rem", fontWeight: 600, color: "var(--fg)", background: "transparent", border: "1px solid currentColor", borderRadius: "999px", cursor: "pointer" }}>
            {t.signOut}
          </button>
        </form>
      </body>
    </html>
  );
}
