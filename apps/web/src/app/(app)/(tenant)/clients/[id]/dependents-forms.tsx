"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field, SelectField, TextAreaField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";

import { addDependent, saveDependent } from "./dependents-actions";

type Definition = components["schemas"]["ClientFieldDefinition"];
type Dependent = components["schemas"]["Dependent"];

type Props = {
  clientId: string;
  kind: "pet" | "child";
  fields: Definition[];
  /** Editing this one; adding a new one when absent. */
  dependent?: Dependent;
};

/** A pet or child: name, date of birth, the industry's details about them and notes. */
export function DependentForm({ clientId, kind, fields, dependent }: Props) {
  const t = useTranslations("dependents");
  const tFields = useTranslations("clientFields");
  const [state, action] = useActionState(
    dependent ? saveDependent.bind(null, clientId, dependent.id) : addDependent.bind(null, clientId),
    {},
  );
  const values = dependent?.details ?? {};
  // Labels are shared with the client fields (clientFields.<key>).
  const label = (key: string) => tFields(key as "goal");

  return (
    <form action={action} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("name")} name="name" required maxLength={80} dir="auto" defaultValue={dependent?.name ?? ""} />
        <Field label={t("birthDate")} name="birth_date" type="date" defaultValue={dependent?.birth_date ?? ""} />
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
                  { value: "", label: tFields("notSet") },
                  ...field.options.map((option) => ({
                    value: option,
                    label: tFields(`${field.key}_options.${option}` as "goal_options.strength"),
                  })),
                ]}
              />
            );
          }
          if (field.kind === "long_text") {
            return (
              <div key={field.key} className="sm:col-span-2">
                <TextAreaField label={label(field.key)} name={name} rows={2} maxLength={field.max_length} defaultValue={value} />
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
        <div className="sm:col-span-2">
          <TextAreaField label={t("notes")} name="notes" rows={2} maxLength={2000} defaultValue={dependent?.notes ?? ""} />
        </div>
      </div>
      <div>
        <SubmitButton>{dependent ? t("save") : t(`add.${kind}`)}</SubmitButton>
      </div>
    </form>
  );
}
