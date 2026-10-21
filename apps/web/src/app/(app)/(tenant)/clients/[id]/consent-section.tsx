"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useActionState } from "react";

import { FormError } from "@/components/form/form-message";
import { SelectField } from "@/components/form/field";
import { SubmitButton } from "@/components/form/submit-button";
import { Badge } from "@/components/ui/badge";
import type { FormState } from "@/lib/form-state";

import { setMarketingConsent } from "./consent-actions";
import { Card } from "@/components/ui/card";

type ConsentSource = "app_join" | "app_profile" | "desk_signed" | "desk_verbal" | "desk_other" | "unsubscribe_link" | "unsubscribe_email";

export type ConsentEvent = {
  id: string;
  action: "granted" | "withdrawn";
  source: ConsentSource;
  recorded_by_name: string | null;
  created_at: string;
};

const DESK_SOURCES = ["desk_signed", "desk_verbal", "desk_other"] as const;

/** Whether the client agreed to marketing messages, how, and when. Staff can record an agreement
 * only with its source, or withdraw it. Service messages (reminders, receipts) are sent either
 * way. */
export function ConsentSection({
  clientId,
  consent,
  optedOut,
  events,
  canWrite,
}: {
  clientId: string;
  consent: boolean;
  optedOut: boolean;
  events: ConsentEvent[];
  canWrite: boolean;
}) {
  const t = useTranslations("clients.consent");
  const format = useFormatter();
  const [state, action] = useActionState<FormState, FormData>(setMarketingConsent.bind(null, clientId, !consent), {});

  return (
    <Card as="section" aria-labelledby="consent-heading" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="consent-heading" className="text-lg font-semibold">
          {t("title")}
        </h2>
        <Badge tone={consent ? "success" : "neutral"} dot>{consent ? t("on") : t("off")}</Badge>
      </div>
      <p className="text-sm text-muted">{t("hint")}</p>
      {optedOut && <p className="text-sm">{t("optedOut")}</p>}
      {canWrite && (
        <form action={action} className="flex flex-col gap-3">
          <FormError message={state.error && (state.error === "invalid" ? t("sourceRequired") : t("error"))} />
          {!consent && (
            <SelectField
              label={t("source")}
              name="source"
              defaultValue=""
              options={[{ value: "", label: t("sourcePick") }, ...DESK_SOURCES.map((s) => ({ value: s, label: t(`sources.${s}`) }))]}
            />
          )}
          <div>
            <SubmitButton variant="secondary" className="px-4 py-2.5">
              {consent ? t("toggleOff") : t("toggleOn")}
            </SubmitButton>
          </div>
        </form>
      )}
      {events.length > 0 && (
        <div className="flex flex-col gap-1">
          <h3 className="text-sm font-medium">{t("history")}</h3>
          <ul className="flex flex-col gap-1 text-sm text-muted">
            {events.map((e) => (
              <li key={e.id}>
                {format.dateTime(new Date(e.created_at), { dateStyle: "medium", timeStyle: "short" })}
                {" · "}
                {t(e.action === "granted" ? "granted" : "withdrawn")}
                {" · "}
                {t(`sources.${e.source}`)}
                {e.recorded_by_name ? ` · ${e.recorded_by_name}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
