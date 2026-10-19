"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { SelectField } from "@/components/form/field";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";

import { setBranchManager } from "./actions";

type Location = components["schemas"]["Location"];

/** Who manages this branch: a team member gets manager rights at this branch only. */
export function BranchManager({ location, members }: { location: Location; members: { id: string; label: string }[] }) {
  const t = useTranslations("locations.manager");
  const tCommon = useTranslations("common");
  const [state, action] = useActionState<FormState, FormData>(setBranchManager.bind(null, location.id), {});

  return (
    <form action={action} className="flex flex-col gap-3">
        <FormError message={state.error && tCommon("errors.generic")} />
        <FormNotice message={state.saved ? tCommon("saved") : undefined} />
        <SelectField
          label={t("label")}
          name="user_id"
          defaultValue={location.manager_user_id ?? ""}
          options={[{ value: "", label: t("none") }, ...members.map((m) => ({ value: m.id, label: m.label }))]}
        />
        <div>
          <SubmitButton>{t("save")}</SubmitButton>
        </div>
    </form>
  );
}
