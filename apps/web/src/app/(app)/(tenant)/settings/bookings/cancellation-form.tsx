"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import { useActionState, useState } from "react";

import { CheckboxField, Field, SelectField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";

import { saveCancellationPolicy, saveOverride } from "./cancellation-actions";

type Overview = components["schemas"]["PolicyOverview"];
type Outcome = "counts" | "recorded";

// Free-cancellation windows offered, in minutes; the current value is added if it is not one.
const PRESETS = [0, 30, 60, 120, 180, 360, 720, 1440, 2880, 4320, 10080];

function useDuration() {
  const t = useTranslations("settings.cancellation");
  return (minutes: number) => {
    if (minutes === 0) return t("durations.anytime");
    if (minutes % 1440 === 0) return t("durations.days", { count: minutes / 1440 });
    if (minutes % 60 === 0) return t("durations.hours", { count: minutes / 60 });
    return t("durations.minutes", { count: minutes });
  };
}

function windowOptions(current: number, label: (minutes: number) => string) {
  return [...new Set([...PRESETS, current])].sort((a, b) => a - b).map((minutes) => ({ value: String(minutes), label: label(minutes) }));
}

function OutcomeSelect({ name, label, value, onChange }: { name: string; label: string; value: Outcome; onChange?: (value: Outcome) => void }) {
  const t = useTranslations("settings.cancellation");
  return (
    <SelectField
      label={label}
      name={name}
      {...(onChange ? { value, onChange: (event: React.ChangeEvent<HTMLSelectElement>) => onChange(event.target.value as Outcome) } : { defaultValue: value })}
      options={(["counts", "recorded"] as const).map((option) => ({ value: option, label: t(`outcomes.${option}`) }))}
    />
  );
}

/** The business-wide terms, with a sentence that changes as the owner picks, so the effect is clear. */
export function CancellationForm({ overview }: { overview: Overview }) {
  const t = useTranslations("settings.cancellation");
  const duration = useDuration();
  const policy = overview.business;
  const [state, action] = useActionState<FormState, FormData>(saveCancellationPolicy, {});
  const [group, setGroup] = useState(policy.group_minutes);
  const [personal, setPersonal] = useState(policy.personal_minutes);
  const [resource, setResource] = useState(policy.resource_minutes);
  const [late, setLate] = useState<Outcome>(policy.late_outcome);
  const [noShow, setNoShow] = useState<Outcome>(policy.no_show_outcome);
  const [limitOn, setLimitOn] = useState(policy.no_show_limit !== null);
  const suggested = overview.suggested;

  return (
    <form action={action} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      {!policy.configured && <p className="rounded-xl bg-primary/5 p-3 text-sm">{t("confirm")}</p>}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <SelectField label={t("group")} name="group_minutes" value={String(group)} onChange={(e) => setGroup(Number(e.target.value))} options={windowOptions(group, duration)} />
        <SelectField label={t("personal")} name="personal_minutes" value={String(personal)} onChange={(e) => setPersonal(Number(e.target.value))} options={windowOptions(personal, duration)} />
        <SelectField label={t("resource")} name="resource_minutes" value={String(resource)} onChange={(e) => setResource(Number(e.target.value))} options={windowOptions(resource, duration)} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <OutcomeSelect name="late_outcome" label={t("lateOutcome")} value={late} onChange={setLate} />
        <OutcomeSelect name="no_show_outcome" label={t("noShowOutcome")} value={noShow} onChange={setNoShow} />
      </div>
      <div className="flex flex-wrap items-end gap-4">
        <CheckboxField label={t("limit")} name="limit_on" checked={limitOn} onChange={(event) => setLimitOn(event.target.checked)} />
        {limitOn && (
          <Field label={t("limitCount")} name="no_show_limit" type="number" min={1} max={30} required defaultValue={policy.no_show_limit ?? 3} />
        )}
      </div>
      <p className="text-xs text-muted">{t("limitHint")}</p>
      <p aria-live="polite" className="rounded-xl bg-surface-muted p-3 text-sm font-medium">
        {t(`live.${late}`, { time: duration(group) })} {group !== personal || group !== resource ? t("liveOthers", { personal: duration(personal), resource: duration(resource) }) : ""}{" "}
        {t(`liveNoShow.${noShow}`)}
      </p>
      <p className="text-xs text-muted">
        {t("suggested", { group: duration(suggested.group_minutes), personal: duration(suggested.personal_minutes) })} {t("feeNote")} {t("lawNote")}
      </p>
      <div>
        <SubmitButton>{policy.configured ? t("save") : t("confirmSave")}</SubmitButton>
      </div>
    </form>
  );
}

type Row = { id: string; name: string; policy: Overview["services"][number]["policy"] };

/** One service or plan that has its own terms; an empty window follows the business. */
export function OverrideRow({ kind, row, fallback }: { kind: "service" | "plan"; row: Row; fallback: Overview["business"] }) {
  const t = useTranslations("settings.cancellation");
  const duration = useDuration();
  const [state, action] = useActionState<FormState, FormData>(saveOverride.bind(null, kind, row.id), {});
  const [custom, setCustom] = useState(row.policy !== null);
  const current = row.policy?.free_minutes ?? fallback.group_minutes;
  return (
    <li className="py-3">
      <form action={action} className="flex flex-wrap items-end gap-3">
        <FormFeedback state={state} />
        <div className="min-w-0 flex-1 basis-48">
          <SelectField
            label={row.name}
            name="free_minutes"
            defaultValue={row.policy ? String(row.policy.free_minutes) : ""}
            onChange={(event) => setCustom(event.target.value !== "")}
            options={[{ value: "", label: t("followBusiness") }, ...windowOptions(current, duration)]}
          />
        </div>
        {custom && (
          <>
            <div className="basis-44">
              <OutcomeSelect name="late_outcome" label={t("lateOutcome")} value={row.policy?.late_outcome ?? fallback.late_outcome} />
            </div>
            <div className="basis-44">
              <OutcomeSelect name="no_show_outcome" label={t("noShowOutcome")} value={row.policy?.no_show_outcome ?? fallback.no_show_outcome} />
            </div>
          </>
        )}
        <SubmitButton variant="secondary" className="px-3 py-2 text-sm">
          {t("saveRow")}
        </SubmitButton>
      </form>
    </li>
  );
}
