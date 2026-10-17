"use client";

import { useTranslations } from "next-intl";
import { useActionState, useState } from "react";

import { BranchScopePicker, type ScopeBranch, type ScopeGroup } from "@/components/branch-scope-picker";
import { Field } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";

type Action = (state: FormState, formData: FormData) => Promise<FormState>;

type Props = {
  branches: ScopeBranch[];
  groups: ScopeGroup[];
  saveGroup: (groupId: string | null, state: FormState, formData: FormData) => Promise<FormState>;
  removeGroup: (groupId: string) => Promise<void>;
};

function GroupForm({
  branches,
  group,
  action,
  onDelete,
}: {
  branches: ScopeBranch[];
  group: ScopeGroup | null;
  action: Action;
  onDelete?: () => void;
}) {
  const t = useTranslations("locations.groups");
  const [state, formAction] = useActionState(action, {});
  const [selected, setSelected] = useState<string[]>(group?.location_ids ?? []);
  return (
    <form action={formAction} className="flex flex-col gap-3 rounded-xl border border-border p-4">
      <FormFeedback state={state} />
      <Field label={t("name")} name="name" defaultValue={group?.name ?? ""} maxLength={60} required />
      <BranchScopePicker branches={branches} groups={[]} value={selected} onChange={setSelected} name="location_id" branchesOnly legend={t("branches")} />
      <div className="flex flex-wrap items-center gap-3">
        <SubmitButton>{group ? t("save") : t("add")}</SubmitButton>
        {onDelete && (
          <button type="button" onClick={onDelete} className="btn-ghost px-3 py-2 text-sm text-danger">
            {t("delete")}
          </button>
        )}
      </div>
    </form>
  );
}

export function LocationGroups({ branches, groups, saveGroup, removeGroup }: Props) {
  const t = useTranslations("locations.groups");
  return (
    <section className="card flex flex-col gap-4 p-5" aria-labelledby="location-groups-heading">
      <div className="flex flex-col gap-1">
        <h2 id="location-groups-heading" className="text-lg font-semibold">
          {t("title")}
        </h2>
        <p className="text-sm text-muted">{t("hint")}</p>
      </div>
      {groups.length === 0 && <p className="text-sm text-muted">{t("empty")}</p>}
      {groups.map((group) => (
        <GroupForm
          key={`${group.id}-${group.name}-${group.location_ids.join()}`}
          branches={branches}
          group={group}
          action={saveGroup.bind(null, group.id)}
          onDelete={() => {
            if (window.confirm(t("confirmDelete", { name: group.name }))) void removeGroup(group.id);
          }}
        />
      ))}
      <details className="rounded-xl">
        <summary className="cursor-pointer text-sm font-medium text-primary-ink">{t("new")}</summary>
        <div className="mt-3">
          <GroupForm branches={branches} group={null} action={saveGroup.bind(null, null)} />
        </div>
      </details>
    </section>
  );
}
