"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useActionState, useState } from "react";

import { Field, SelectField, TextAreaField } from "@/components/form/field";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { isDay, toApiWeekday, weekdayOf as jsWeekday } from "@/lib/dates";

import type { SessionFormState } from "./actions";

type Options = components["schemas"]["ScheduleOptions"];

export type SessionDefaults = {
  service_id?: string;
  date: string;
  start_time?: string;
  duration_minutes?: number;
  capacity?: number;
  place?: string;
  instructor_user_id?: string | null;
  notes?: string | null;
};

type Props = {
  action: (state: SessionFormState, formData: FormData) => Promise<SessionFormState>;
  options: Options;
  defaults: SessionDefaults;
  submitLabel: string;
  allowRepeat?: boolean;
  lockService?: boolean;
  readOnly?: boolean;
};

export function SessionForm({ action, options, defaults, submitLabel, allowRepeat, lockService, readOnly }: Props) {
  const t = useTranslations();
  const [state, formAction] = useActionState(action, {});
  const [repeat, setRepeat] = useState(false);
  const [serviceId, setServiceId] = useState(defaults.service_id ?? options.services[0]?.id ?? "");
  const service = options.services.find((s) => s.id === serviceId);
  // Repeat days follow the chosen date, so the first session always falls on that date
  // unless the user deliberately unchecks its weekday.
  const [date, setDate] = useState(defaults.date);
  const [weekdays, setWeekdays] = useState<number[]>([jsWeekday(defaults.date)]);
  const changeDate = (next: string) => {
    if (!isDay(next)) return setDate(next);
    const [previous, added] = [jsWeekday(date), jsWeekday(next)];
    setWeekdays((days) => {
      const kept = days.length === 1 && days[0] === previous ? [] : days;
      return kept.includes(added) ? kept : [...kept, added];
    });
    setDate(next);
  };

  const places = [
    { value: "", label: t("schedule.none") },
    ...options.locations.flatMap((location) => [
      { value: `${location.id}:`, label: location.name },
      ...options.rooms
        .filter((room) => room.location_id === location.id)
        .map((room) => ({ value: `${location.id}:${room.id}`, label: `${location.name} · ${room.name}` })),
    ]),
  ];
  const errorMessage =
    state.error === "invalid_reference" || state.error === "no_occurrences"
      ? t(`schedule.errors.${state.error}`)
      : state.error && t(`common.errors.${state.error}`);

  return (
    <form action={formAction} className="flex flex-col gap-4">
      <FormError message={errorMessage} />
      <FormNotice message={state.saved ? t("common.saved") : undefined} />
      <fieldset disabled={readOnly} className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <SelectField
            label={t("schedule.service")}
            name="service_id"
            value={serviceId}
            disabled={lockService}
            onChange={(event) => setServiceId(event.target.value)}
            options={options.services.map((s) => ({ value: s.id, label: s.name }))}
          />
        </div>
        <Field
          label={t("schedule.date")}
          name="date"
          type="date"
          required
          value={date}
          onChange={(event) => changeDate(event.target.value)}
        />
        <Field label={t("schedule.startTime")} name="start_time" type="time" required step={300} defaultValue={defaults.start_time ?? "18:00"} />
        <Field
          label={t("schedule.duration")}
          hint={t("schedule.durationHint")}
          name="duration_minutes"
          type="number"
          min={5}
          max={1440}
          placeholder={String(service?.duration_minutes ?? "")}
          defaultValue={defaults.duration_minutes}
        />
        <Field
          label={t("schedule.capacity")}
          hint={t("schedule.capacityHint")}
          name="capacity"
          type="number"
          min={1}
          max={1000}
          placeholder={String(service?.capacity ?? "")}
          defaultValue={defaults.capacity}
        />
        <SelectField label={t("schedule.room")} name="place" defaultValue={defaults.place ?? ""} options={places} />
        <SelectField
          label={t("schedule.instructor")}
          name="instructor_user_id"
          defaultValue={defaults.instructor_user_id ?? ""}
          options={[
            { value: "", label: t("schedule.none") },
            ...options.instructors.map((i) => ({ value: i.user_id, label: i.full_name ?? i.email })),
          ]}
        />
        <div className="sm:col-span-2">
          <TextAreaField label={t("schedule.notes")} name="notes" maxLength={2000} defaultValue={defaults.notes ?? ""} />
        </div>
      </fieldset>

      {allowRepeat && (
        <fieldset className="flex flex-col gap-3 rounded-xl border border-border p-4">
          <label className="flex items-center gap-2 text-sm font-medium">
            <input type="checkbox" name="repeat" checked={repeat} onChange={(e) => setRepeat(e.target.checked)} className="size-4 accent-primary" />
            {t("schedule.repeat")}
          </label>
          {repeat && (
            <>
              <div role="group" aria-label={t("schedule.repeatOn")} className="flex flex-wrap gap-2">
                {[0, 1, 2, 3, 4, 5, 6].map((day) => (
                  <label key={day} className="flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-sm">
                    <input
                      type="checkbox"
                      name="weekdays"
                      value={toApiWeekday(day)}
                      checked={weekdays.includes(day)}
                      onChange={(event) =>
                        setWeekdays((days) =>
                          event.target.checked ? [...days, day] : days.filter((d) => d !== day),
                        )
                      }
                      className="size-4 accent-primary"
                    />
                    {t(`schedule.weekdays.${day}` as "schedule.weekdays.0")}
                  </label>
                ))}
              </div>
              <Field label={t("schedule.repeatUntil")} hint={t("schedule.repeatUntilHint")} name="ends_on" type="date" />
            </>
          )}
        </fieldset>
      )}

      {!readOnly && (
        <div className="flex items-center gap-4">
          <SubmitButton>{submitLabel}</SubmitButton>
          <Link href="/schedule" className="text-sm text-muted underline-offset-4 hover:underline">
            {t("common.cancel")}
          </Link>
        </div>
      )}
    </form>
  );
}
