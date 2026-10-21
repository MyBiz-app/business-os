"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field, SelectField } from "@/components/form/field";
import { FormError, FormNotice } from "@/components/form/form-message";

import { saveRules } from "./actions";
import { Button } from "@/components/ui/button";

type Rules = {
  work_days_per_week: number;
  week_hours: number;
  day_hours_5: number;
  day_hours_6: number;
  tier1_hours: number;
  tier1_percent: number;
  tier2_percent: number;
  rest_day_percent: number;
  rest_weekday: number;
};

/** The overtime rules of the business (a 42 hour week, 125% then 150% by default). */
export function RulesForm({ rules, canEdit, locale }: { rules: Rules; canEdit: boolean; locale: string }) {
  const t = useTranslations("timeClock");
  const [state, action, pending] = useActionState(saveRules, {});
  // Monday = 0, matching the API; 2024-01-01 was a Monday.
  const weekdays = Array.from({ length: 7 }, (_, day) => ({
    value: String(day),
    label: new Intl.DateTimeFormat(locale, { weekday: "long", timeZone: "UTC" }).format(new Date(Date.UTC(2024, 0, 1 + day))),
  }));
  const number = (name: keyof Rules, label: string, step = "1") => (
    <Field label={label} name={name} type="number" step={step} min="0" defaultValue={rules[name]} disabled={!canEdit} required />
  );
  return (
    <form action={action} className="grid gap-4 sm:grid-cols-2">
      <FormError message={state.error && (t.has(`errors.${state.error}` as "errors.generic") ? t(`errors.${state.error}` as "errors.generic") : t("errors.generic"))} />
      <FormNotice message={state.saved ? t("rules.saved") : undefined} />
      <SelectField
        label={t("rules.workDays")}
        name="work_days_per_week"
        defaultValue={String(rules.work_days_per_week)}
        disabled={!canEdit}
        options={[
          { value: "5", label: "5" },
          { value: "6", label: "6" },
        ]}
      />
      {number("week_hours", t("rules.weekHours"), "0.5")}
      {number("day_hours_5", t("rules.day5"), "0.1")}
      {number("day_hours_6", t("rules.day6"), "0.1")}
      {number("tier1_hours", t("rules.tier1Hours"), "0.5")}
      {number("tier1_percent", t("rules.tier1Percent"))}
      {number("tier2_percent", t("rules.tier2Percent"))}
      {number("rest_day_percent", t("rules.restPercent"))}
      <SelectField label={t("rules.restWeekday")} name="rest_weekday" defaultValue={String(rules.rest_weekday)} disabled={!canEdit} options={weekdays} />
      {canEdit && (
        <div className="sm:col-span-2">
          <Button variant="primary" type="submit" disabled={pending}>
            {t("rules.save")}
          </Button>
        </div>
      )}
    </form>
  );
}
