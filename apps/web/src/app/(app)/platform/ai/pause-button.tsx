"use client";

import { Pause, Play } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState, useTransition } from "react";

import { FormError } from "@/components/form/form-message";

import { setBusinessAiPaused } from "./actions";
import { Button } from "@/components/ui/button";

/** Stops AI for one business (asks for a reason, which both audit logs keep) or resumes it. */
export function PauseButton({ tenantId, name, paused }: { tenantId: string; name: string; paused: boolean }) {
  const t = useTranslations("platform.ai");
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string>();
  const [pending, start] = useTransition();

  const run = (next: boolean) =>
    start(async () => {
      const result = await setBusinessAiPaused(tenantId, next, reason.trim());
      setError(result.error ? t(`errors.${result.error}` as "errors.generic") : undefined);
      if (!result.error) {
        setAsking(false);
        setReason("");
      }
    });

  if (paused) {
    return (
      <>
        <FormError message={error} toastOnly />
        <Button disabled={pending} onClick={() => run(false)} className="inline-flex items-center gap-1.5">
          <Play aria-hidden="true" className="size-4" />
          {t("resume")}
        </Button>
      </>
    );
  }
  if (!asking) {
    return (
      <Button onClick={() => setAsking(true)} aria-label={t("pauseFor", { name })} className="inline-flex items-center gap-1.5">
        <Pause aria-hidden="true" className="size-4" />
        {t("pause")}
      </Button>
    );
  }
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        run(true);
      }}
      className="flex flex-wrap items-center gap-2"
    >
      <FormError message={error} toastOnly />
      <input
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        required
        minLength={3}
        maxLength={500}
        aria-label={t("reason")}
        placeholder={t("reason")}
        className="control min-w-40 px-3 py-1.5 text-sm"
      />
      <Button variant="danger" type="submit" disabled={pending || reason.trim().length < 3}>
        {t("pause")}
      </Button>
      <Button onClick={() => setAsking(false)}>
        {t("cancel")}
      </Button>
    </form>
  );
}
