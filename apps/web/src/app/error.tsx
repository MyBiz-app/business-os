"use client";

import * as Sentry from "@sentry/nextjs";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import { Container } from "@/components/layout/container";

/** Shown when a page crashes while rendering: a translated message, a way to retry and the
 * error digest, which support can match to the server log. */
export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useTranslations("errorPages");
  const common = useTranslations("common");

  useEffect(() => {
    Sentry.captureException(error);
    console.error(error);
  }, [error]);

  return (
    <Container as="main" size="prose" className="flex max-w-md flex-1 flex-col items-center justify-center gap-4 py-16 text-center">
      <h1 className="text-2xl font-semibold">{t("title")}</h1>
      <p className="text-muted">{t("text")}</p>
      {error.digest ? (
        <p className="text-sm text-muted" dir="ltr">
          {t("reference", { code: error.digest })}
        </p>
      ) : null}
      <div className="flex flex-wrap justify-center gap-3">
        <button type="button" onClick={reset} className="btn-primary px-4 py-2">
          {common("retry")}
        </button>
        {/* A plain link: the router itself may be what failed. */}
        {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
        <a href="/" className="btn-ghost px-4 py-2">
          {t("home")}
        </a>
      </div>
    </Container>
  );
}
