"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field, SelectField, TextAreaField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";

import { addNote, saveProfile } from "./profile-actions";

type Definition = components["schemas"]["ClientFieldDefinition"];

type ProfileProps = {
  clientId: string;
  vertical: string;
  fields: Definition[];
  values: Record<string, string | number>;
  readOnly: boolean;
};

/** The vertical pack's extra client fields, as a form. */
export function ProfileForm({ clientId, vertical, fields, values, readOnly }: ProfileProps) {
  const t = useTranslations("fields");
  const tCommon = useTranslations("clients");
  const [state, action] = useActionState(saveProfile.bind(null, clientId), {});
  const label = (key: string) => t(`${vertical}.${key}` as "fitness.goal");

  return (
    <form action={action} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      <fieldset disabled={readOnly} className="grid gap-4 sm:grid-cols-2">
        {fields.map((field) => {
          const name = `field.${field.key}`;
          const value = values[field.key] === undefined ? "" : String(values[field.key]);
          if (field.kind === "select") {
            return (
              <SelectField
                key={field.key}
                label={label(field.key)}
                name={name}
                defaultValue={value}
                options={[
                  { value: "", label: t("notSet") },
                  ...field.options.map((option) => ({
                    value: option,
                    label: t(`${vertical}.${field.key}_options.${option}` as "fitness.goal_options.strength"),
                  })),
                ]}
              />
            );
          }
          if (field.kind === "long_text") {
            return (
              <div key={field.key} className="sm:col-span-2">
                <TextAreaField label={label(field.key)} name={name} rows={3} maxLength={field.max_length} defaultValue={value} />
              </div>
            );
          }
          return (
            <Field
              key={field.key}
              label={label(field.key)}
              name={name}
              type={field.kind === "number" ? "number" : field.kind === "date" ? "date" : "text"}
              min={field.kind === "number" ? 0 : undefined}
              maxLength={field.kind === "text" ? field.max_length : undefined}
              dir={field.kind === "text" ? "auto" : undefined}
              defaultValue={value}
            />
          );
        })}
      </fieldset>
      {!readOnly && (
        <div>
          <SubmitButton>{tCommon("save")}</SubmitButton>
        </div>
      )}
    </form>
  );
}

type NoteProps = {
  clientId: string;
  bookings: { id: string; label: string }[];
};

export function NoteForm({ clientId, bookings }: NoteProps) {
  const t = useTranslations("visitNotes");
  const [state, action] = useActionState(addNote.bind(null, clientId), {});
  return (
    <form action={action} className="flex flex-col gap-3 rounded-xl bg-foreground/[0.03] p-3">
      <FormFeedback state={state.error ? state : {}} />
      <TextAreaField label={t("body")} name="body" required maxLength={5000} rows={3} />
      {bookings.length > 0 && (
        <SelectField
          label={t("about")}
          name="booking_id"
          defaultValue=""
          options={[{ value: "", label: t("general") }, ...bookings.map((b) => ({ value: b.id, label: b.label }))]}
        />
      )}
      <div>
        <SubmitButton>{t("add")}</SubmitButton>
      </div>
    </form>
  );
}
