"use client";

import { useTranslations } from "next-intl";
import { useId } from "react";

export type ScopeBranch = { id: string; name: string };
export type ScopeGroup = { id: string; name: string; location_ids: string[] };

type Props = {
  branches: ScopeBranch[];
  groups: ScopeGroup[];
  /** The selected branch ids (the resolved scope: a group or "all" is just a quick way to pick). */
  value: string[];
  onChange: (value: string[]) => void;
  /** Adds one hidden `<input>` per selected branch with this name, for plain forms. */
  name?: string;
  /** Hide the "all branches" and group shortcuts (a single set of branches is picked). */
  branchesOnly?: boolean;
  legend?: string;
};

const sameSet = (a: string[], b: string[]) => a.length === b.length && a.every((id) => b.includes(id));

/** Picks the branches a screen, message or AI agent applies to: the whole network, a group, or
 * individual branches. Groups and "all" only select branches, so the result is always a list. */
export function BranchScopePicker({ branches, groups, value, onChange, name, branchesOnly = false, legend }: Props) {
  const t = useTranslations("locations.scope");
  const id = useId();
  const allIds = branches.map((branch) => branch.id);
  const known = new Set(allIds);
  const toggle = (branchId: string) =>
    onChange(value.includes(branchId) ? value.filter((v) => v !== branchId) : [...value, branchId]);

  const shortcuts = [
    { key: "all", label: t("all"), ids: allIds },
    ...groups.map((group) => ({ key: group.id, label: group.name, ids: group.location_ids.filter((v) => known.has(v)) })),
  ];

  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="mb-1 text-sm font-medium">{legend ?? t("legend")}</legend>
      {!branchesOnly && (
        <div className="flex flex-wrap gap-2">
          {shortcuts.map((shortcut) => (
            <button
              key={shortcut.key}
              type="button"
              aria-pressed={shortcut.ids.length > 0 && sameSet(value, shortcut.ids)}
              disabled={shortcut.ids.length === 0}
              onClick={() => onChange(shortcut.ids)}
              dir="auto"
              className="btn-plain rounded-full border border-border px-3 py-1 text-sm aria-pressed:border-primary aria-pressed:bg-primary/10 aria-pressed:text-primary-ink disabled:opacity-50"
            >
              {shortcut.label}
            </button>
          ))}
        </div>
      )}
      <ul className="grid gap-2 sm:grid-cols-2">
        {branches.map((branch) => (
          <li key={branch.id}>
            <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-border p-2.5 has-[:checked]:border-primary has-[:checked]:bg-primary/5">
              <input
                type="checkbox"
                checked={value.includes(branch.id)}
                onChange={() => toggle(branch.id)}
                aria-describedby={`${id}-count`}
              />
              <span dir="auto">{branch.name}</span>
            </label>
          </li>
        ))}
      </ul>
      <p id={`${id}-count`} className="text-xs text-muted" aria-live="polite">
        {t("count", { selected: value.length, total: branches.length })}
      </p>
      {name && value.map((branchId) => <input key={branchId} type="hidden" name={name} value={branchId} />)}
    </fieldset>
  );
}
