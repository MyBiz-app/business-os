"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";

import { ChoiceCard } from "@/components/form/choice-card";
import { SelectField, TextAreaField } from "@/components/form/field";
import { SubmitButton } from "@/components/form/submit-button";

import { cancelSubscription, pauseSubscription } from "../actions";

const REASONS = ["too_expensive", "missing_feature", "not_using", "switched", "other"] as const;
const STEPS = ["reason", "offer", "confirm"] as const;
type Step = (typeof STEPS)[number];

type Props = {
  endsOn: string;
  /** The first payment given back (formatted), when the policy gives it. */
  refund: string | null;
  pause: { available: boolean; fee: string; maxMonths: number };
};

/** Three short steps. Nothing changes until the last one; the answers are kept in the page so going
 * back loses nothing, and the final form carries them to the server. */
export function CancelFlow({ endsOn, refund, pause }: Props) {
  const t = useTranslations("billing.cancelFlow");
  const [step, setStep] = useState<Step>("reason");
  const [reason, setReason] = useState<string>("");
  const [note, setNote] = useState("");
  const index = STEPS.indexOf(step);

  return (
    <div className="flex flex-col gap-5">
      <ol className="flex flex-wrap gap-2 text-sm" aria-label={t("title")}>
        {STEPS.map((item, position) => (
          <li
            key={item}
            aria-current={item === step ? "step" : undefined}
            className={`rounded-full px-3 py-1 font-medium ${item === step ? "bg-primary/10 text-primary-ink" : "text-muted"}`}
          >
            {position + 1}. {t(`steps.${item}`)}
          </li>
        ))}
      </ol>

      {step === "reason" && (
        <fieldset className="flex flex-col gap-3">
          <legend className="text-lg font-semibold">{t("reasonTitle")}</legend>
          <p className="text-sm text-muted">{t("reasonHint")}</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {REASONS.map((item) => (
              <ChoiceCard
                key={item}
                type="radio"
                name="reason-choice"
                title={t(`reasons.${item}`)}
                checked={reason === item}
                onChange={() => setReason(item)}
              />
            ))}
          </div>
          <TextAreaField label={t("noteLabel")} value={note} maxLength={1000} rows={3} onChange={(event) => setNote(event.target.value)} />
          <div>
            <button type="button" className="btn-primary px-4 py-2.5" onClick={() => setStep("offer")}>
              {t("continue")}
            </button>
          </div>
        </fieldset>
      )}

      {step === "offer" && (
        <section className="flex flex-col gap-4" aria-labelledby="offer-title">
          <h2 id="offer-title" className="text-lg font-semibold">{t("offerTitle")}</h2>
          <div className="card flex flex-col gap-3 p-4">
            <h3 className="font-semibold">{t("offerPauseTitle")}</h3>
            {pause.available ? (
              <form action={pauseSubscription} className="flex flex-col gap-3">
                <p className="text-sm text-muted">{t("offerPauseText", { fee: pause.fee, months: pause.maxMonths })}</p>
                <input type="hidden" name="reason" value={reason} />
                <SelectField
                  label={t("offerPauseMonths")}
                  name="months"
                  defaultValue="1"
                  options={Array.from({ length: pause.maxMonths }, (_, i) => ({
                    value: String(i + 1),
                    label: t("offerPauseMonthsValue", { count: i + 1 }),
                  }))}
                />
                <div>
                  <SubmitButton variant="secondary">{t("offerPauseCta")}</SubmitButton>
                </div>
              </form>
            ) : (
              <p className="text-sm text-muted">{t("offerPauseUnavailable")}</p>
            )}
          </div>
          <div className="card flex flex-col gap-3 p-4">
            <h3 className="font-semibold">{t("offerModulesTitle")}</h3>
            <p className="text-sm text-muted">{t("offerModulesText")}</p>
            <div>
              <Link href="/settings/modules" className="btn-secondary px-4 py-2.5">
                {t("offerModulesCta")}
              </Link>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-secondary px-4 py-2.5" onClick={() => setStep("reason")}>
              {t("back")}
            </button>
            <button type="button" className="btn-primary px-4 py-2.5" onClick={() => setStep("confirm")}>
              {t("continue")}
            </button>
          </div>
        </section>
      )}

      {step === "confirm" && (
        <form action={cancelSubscription} className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold">{t("confirmTitle")}</h2>
          <input type="hidden" name="reason" value={reason} />
          <input type="hidden" name="note" value={note} />
          <ul className="flex list-disc flex-col gap-1.5 ps-5 text-sm">
            <li>{t("confirmEnds", { date: endsOn })}</li>
            <li>{refund ? t("confirmRefund", { amount: refund }) : t("confirmNoRefund")}</li>
            <li>{t("confirmData")}</li>
          </ul>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-secondary px-4 py-2.5" onClick={() => setStep("offer")}>
              {t("back")}
            </button>
            <SubmitButton variant="danger">{t("confirmCta")}</SubmitButton>
            <Link href="/settings/billing" className="btn-secondary px-4 py-2.5">
              {t("keep")}
            </Link>
          </div>
        </form>
      )}
      <span className="sr-only" aria-live="polite">{t(`steps.${STEPS[index]}`)}</span>
    </div>
  );
}
