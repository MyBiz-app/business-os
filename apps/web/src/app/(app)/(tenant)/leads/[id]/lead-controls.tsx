"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import { useActionState, useState } from "react";

import { SelectField, TextAreaField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";

import { addActivity, changeStage } from "../actions";

type Stage = components["schemas"]["Lead"]["stage"];
const OPEN: Stage[] = ["new", "contacted", "trial", "offer"];

/** The open stages as steps; "lost" asks for a reason. "Won" is reached by converting. */
export function StageControl({ leadId, stage, lostReason }: { leadId: string; stage: Stage; lostReason: string | null }) {
  const t = useTranslations("leads");
  const [state, action, pending] = useActionState(changeStage.bind(null, leadId), {});
  const [losing, setLosing] = useState(false);
  const current = OPEN.indexOf(stage);

  return (
    <div className="flex flex-col gap-3">
      <FormFeedback state={state.error ? state : {}} />
      <form action={action} className="flex flex-col gap-3">
        <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {OPEN.map((step, index) => {
            const active = step === stage;
            const done = current >= 0 && index < current;
            return (
              <li key={step}>
                <button
                  type="submit"
                  name="stage"
                  value={step}
                  disabled={pending || active}
                  aria-current={active ? "step" : undefined}
                  className={`flex w-full items-center gap-2 rounded-xl border px-3 py-2.5 text-start text-sm font-medium transition ${
                    active
                      ? "border-primary bg-primary text-on-primary"
                      : done
                        ? "border-primary/40 bg-primary/10 hover:bg-primary/15"
                        : "border-border bg-surface hover:border-primary/50"
                  }`}
                >
                  <span aria-hidden="true" className="tabular-nums opacity-70">{index + 1}</span>
                  {t(`stages.${step}`)}
                </button>
              </li>
            );
          })}
        </ol>
      </form>
      {stage === "lost" ? (
        <p className="text-sm">
          <span className="font-medium">{t("stages.lost")}</span>
          {lostReason && <span dir="auto" className="text-muted"> · {lostReason}</span>}
        </p>
      ) : losing ? (
        <form action={action} className="flex flex-wrap items-end gap-3">
          <input type="hidden" name="stage" value="lost" />
          <label className="flex min-w-60 flex-1 flex-col gap-1.5 text-sm font-medium">
            {t("lostReason")}
            <input name="lost_reason" maxLength={500} className="control px-3 py-2 font-normal" />
          </label>
          <SubmitButton>{t("markLost")}</SubmitButton>
          <button type="button" onClick={() => setLosing(false)} className="text-sm text-muted underline-offset-4 hover:underline">
            {t("cancel")}
          </button>
        </form>
      ) : (
        <button type="button" onClick={() => setLosing(true)} className="self-start text-sm text-muted underline-offset-4 hover:underline">
          {t("markLost")}
        </button>
      )}
    </div>
  );
}

const KINDS = ["call", "message", "meeting", "note"] as const;

export function ActivityForm({ leadId }: { leadId: string }) {
  const t = useTranslations("leads");
  const [state, action] = useActionState(addActivity.bind(null, leadId), {});
  return (
    <form action={action} className="flex flex-col gap-3 rounded-xl bg-foreground/[0.03] p-3">
      <FormFeedback state={state.error ? state : {}} />
      <div className="grid gap-3 sm:grid-cols-[10rem_1fr]">
        <SelectField
          label={t("activityKind")}
          name="kind"
          defaultValue="call"
          options={KINDS.map((value) => ({ value, label: t(`activities.${value}`) }))}
        />
        <TextAreaField label={t("activityNote")} name="note" required maxLength={2000} rows={2} />
      </div>
      <div>
        <SubmitButton>{t("logActivity")}</SubmitButton>
      </div>
    </form>
  );
}
