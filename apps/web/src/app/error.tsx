"use client";

import * as Sentry from "@sentry/nextjs";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import { StatusPage } from "@/components/layout/status-page";

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
    <StatusPage
      title={t("title")}
      text={t("text")}
      detail={
        error.digest ? (
          <p className="text-sm text-muted" dir="ltr">
            {t("reference", { code: error.digest })}
          </p>
        ) : null
      }
    >
      <button type="button" onClick={reset} className="btn-primary rounded-full px-6 py-2.5">
        {common("retry")}
      </button>
      {/* A plain link: the router itself may be what failed. */}
      {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
      <a href="/" className="btn-secondary rounded-full px-6 py-2.5">
        {t("home")}
      </a>
    </StatusPage>
  );
}
