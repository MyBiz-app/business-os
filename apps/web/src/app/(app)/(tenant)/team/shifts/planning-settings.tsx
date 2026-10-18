"use client";

import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { Settings2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState, useState } from "react";

import { SubmitButton } from "@/components/form/submit-button";

import { type PlanningState, savePlanning } from "./actions";
import { FormError, FormNotice } from "@/components/form/form-message";

type Branch = { id: string; name: string; color: string; cadence: "daily" | "weekly" | "monthly" | "custom"; days: number | null };

/** How often each branch plans its shifts. The board opens on that window for the branch. */
export function PlanningSettings({ branches }: { branches: Branch[] }) {
  const t = useTranslations("shifts");
  return (
    <CollapsibleSection
      icon={<Settings2 aria-hidden="true" className="size-4 text-primary-ink" />}
      title={t("planning.title")}
      description={t("planning.hint")}
      storageKey="shifts-planning"
    >
      <ul className="-mx-5 -my-5 flex flex-col divide-y divide-border">
        {branches.map((branch) => (
          <PlanningRow key={branch.id} branch={branch} />
        ))}
      </ul>
    </CollapsibleSection>
  );
}

function PlanningRow({ branch }: { branch: Branch }) {
  const t = useTranslations("shifts");
  const [state, action] = useActionState<PlanningState, FormData>(savePlanning.bind(null, branch.id), {});
  const [cadence, setCadence] = useState(branch.cadence);
  return (
    <li>
      <form action={action} className="flex flex-wrap items-center gap-3 px-5 py-3">
        <span className="flex min-w-40 flex-1 items-center gap-2 font-medium">
          <span aria-hidden="true" className="size-2.5 rounded-full" style={{ background: branch.color }} />
          <span dir="auto">{branch.name}</span>
        </span>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted">{t("planning.cadence")}</span>
          <select name="cadence" value={cadence} onChange={(e) => setCadence(e.target.value as Branch["cadence"])} className="control px-2 py-1.5">
            {(["daily", "weekly", "monthly", "custom"] as const).map((c) => (
              <option key={c} value={c}>
                {t(`planning.cadences.${c}`)}
              </option>
            ))}
          </select>
        </label>
        {cadence === "custom" && (
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted">{t("planning.days")}</span>
            <input name="days" type="number" min={1} max={42} defaultValue={branch.days ?? 14} required dir="ltr" className="control w-20 px-2 py-1.5" />
          </label>
        )}
        <SubmitButton className="px-3 py-1.5 text-sm">{t("planning.save")}</SubmitButton>
        <FormNotice message={state.saved ? t("planning.saved") : undefined} />
        <FormError toastOnly message={state.error ? t("errors.invalid") : undefined} />
      </form>
    </li>
  );
}
