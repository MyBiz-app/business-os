"use client";

import { DoorOpen, Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState, useTransition } from "react";

import { deleteStation, renameStation, saveStation, type StationState } from "./actions";
import { ToastOnChange } from "@/components/toast/toaster";

type Branch = { id: string; name: string; color: string; stations: { id: string; name: string }[] };

/** The rooms, desks or posts of each branch that shifts are planned into ("Pilates 1", "Yoga 2").
 * The owner defines their own; a branch without any is planned as a whole, as before. */
export function StationSettings({ branches }: { branches: Branch[] }) {
  const t = useTranslations("shifts");
  return (
    <details className="card group p-0">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-5 py-3 font-medium [&::-webkit-details-marker]:hidden">
        <DoorOpen aria-hidden="true" className="size-4 text-primary" />
        {t("stations.title")}
        <span className="ms-2 text-sm font-normal text-muted">{t("stations.hint")}</span>
      </summary>
      <ul className="flex flex-col divide-y divide-border border-t border-border">
        {branches.map((branch) => (
          <StationBranch key={branch.id} branch={branch} />
        ))}
      </ul>
    </details>
  );
}

function StationBranch({ branch }: { branch: Branch }) {
  const t = useTranslations("shifts");
  const [name, setName] = useState("");
  const [state, setState] = useState<StationState>({});
  const [pending, start] = useTransition();
  const message = state.error ? (state.error === "name_taken" ? t("stations.nameTaken") : t("errors.invalid")) : "";
  const run = (job: () => Promise<StationState | void>) =>
    start(async () => {
      const result = await job();
      if (result) setState(result);
    });
  return (
    <li className="flex flex-col gap-3 px-5 py-4">
      <span className="flex items-center gap-2 font-medium">
        <span aria-hidden="true" className="size-2.5 rounded-full" style={{ background: branch.color }} />
        <span dir="auto">{branch.name}</span>
      </span>
      {branch.stations.length === 0 && <p className="text-sm text-muted">{t("stations.none")}</p>}
      {branch.stations.map((station) => (
        <div key={station.id} className="flex items-center gap-2">
          <input
            defaultValue={station.name}
            aria-label={t("stations.name")}
            maxLength={40}
            dir="auto"
            onBlur={(e) => {
              const next = e.target.value.trim();
              if (next && next !== station.name) run(() => renameStation(station.id, next));
              else e.target.value = station.name;
            }}
            className="control min-w-0 flex-1 px-3 py-1.5 text-sm"
          />
          <button type="button" disabled={pending} onClick={() => run(() => deleteStation(station.id))} aria-label={t("stations.remove", { name: station.name })} title={t("stations.removeHint")} className="btn-ghost size-9">
            <Trash2 aria-hidden="true" className="size-4" />
          </button>
        </div>
      ))}
      <form
        className="flex items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const next = name.trim();
          if (!next) return;
          run(async () => {
            const result = await saveStation(branch.id, next);
            if (result.saved) setName("");
            return result;
          });
        }}
      >
        <input value={name} onChange={(e) => setName(e.target.value)} aria-label={t("stations.name")} placeholder={t("stations.namePlaceholder")} maxLength={40} dir="auto" className="control min-w-0 flex-1 px-3 py-1.5 text-sm" />
        <button type="submit" disabled={pending || !name.trim()} aria-busy={pending} className="btn-secondary px-3 py-1.5 text-sm">
          <Plus aria-hidden="true" className="size-4" />
          {t("stations.add")}
        </button>
      </form>
      <ToastOnChange source={state} tone="error" message={message || undefined} />
    </li>
  );
}
