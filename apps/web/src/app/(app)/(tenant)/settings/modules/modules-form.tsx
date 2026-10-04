"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import { type Catalog, ModulePicker, type Selection } from "@/components/modules/module-picker";
import type { FormState } from "@/lib/form-state";

import { saveModules } from "./actions";

type Props = { catalog: Catalog; selection: Selection; activeClients: number };

export function ModulesForm({ catalog, selection, activeClients }: Props) {
  const t = useTranslations();
  const [state, action] = useActionState<FormState, FormData>(saveModules, {});
  return (
    <form action={action} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      <ModulePicker catalog={catalog} initial={selection} activeClients={activeClients} name="modules" />
      <div>
        <SubmitButton>{t("common.save")}</SubmitButton>
      </div>
    </form>
  );
}
