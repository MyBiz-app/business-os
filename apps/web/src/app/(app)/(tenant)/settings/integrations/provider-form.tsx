"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import { useActionState, useState } from "react";

import { Field, SelectField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";

import { connectProvider } from "./actions";

type Integration = components["schemas"]["Integration"];

/** Choose a provider and fill its settings; secrets already set are kept when left empty. */
export function ProviderForm({ integration }: { integration: Integration }) {
  const t = useTranslations("integrations");
  const [state, action] = useActionState(connectProvider.bind(null, integration.capability), {});
  const [name, setName] = useState(integration.provider);
  const option = integration.options.find((o) => o.name === name) ?? integration.options[0];
  const same = name === integration.provider && integration.own;

  return (
    <form action={action} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      <SelectField
        label={t("provider")}
        name="provider"
        value={name}
        onChange={(event) => setName(event.target.value)}
        options={integration.options.map((o) => ({ value: o.name, label: o.builtin ? `${o.label} · ${t("builtin")}` : o.label }))}
      />
      {option?.description && <p className="text-sm text-muted">{option.description}</p>}
      {option && option.fields.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          {option.fields.map((field) => {
            const isSet = same && integration.secrets_set.includes(field.key);
            return (
              <Field
                key={`${option.name}-${field.key}`}
                label={field.label}
                name={`setting.${field.key}`}
                type={field.secret ? "password" : "text"}
                autoComplete="off"
                dir="ltr"
                required={field.required && !isSet}
                placeholder={isSet ? t("secretSet") : undefined}
                hint={field.secret ? (isSet ? t("secretKeep") : t("secretHint")) : undefined}
                defaultValue={!field.secret && same ? (integration.settings[field.key] ?? "") : ""}
              />
            );
          })}
        </div>
      )}
      <div>
        <SubmitButton>{t("save")}</SubmitButton>
      </div>
    </form>
  );
}
