"use client";

import { Building2, Check } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef } from "react";

export type Branch = { id: string; name: string };

/** Which branches an agent looks at in this chat: the whole network, or only the ticked ones. The API still caps it to the branches the person may see. */
export function ScopePicker({ branches, value, onChange }: { branches: Branch[]; value: string[] | null; onChange: (ids: string[] | null) => void }) {
  const t = useTranslations("aiTeam");
  const details = useRef<HTMLDetailsElement>(null);
  if (branches.length < 2) return null;
  const label = value === null ? t("scope.all") : value.length === 1 ? (branches.find((b) => b.id === value[0])?.name ?? t("scope.some", { count: 1 })) : t("scope.some", { count: value.length });
  const toggle = (id: string) => {
    const next = new Set(value ?? branches.map((b) => b.id));
    if (next.has(id)) next.delete(id);
    else next.add(id);
    // Nothing left ticked is not a scope: fall back to everything. All ticked is the same as everything.
    onChange(next.size === 0 || next.size === branches.length ? null : [...next]);
  };
  return (
    <details ref={details} className="relative" onKeyDown={(e) => e.key === "Escape" && details.current?.removeAttribute("open")}>
      <summary className="btn-secondary inline-flex cursor-pointer list-none items-center gap-2 px-3 py-1.5 text-sm [&::-webkit-details-marker]:hidden" aria-label={t("scope.label")}>
        <Building2 aria-hidden="true" className="size-4" />
        <span className="max-w-[10rem] truncate" dir="auto">
          {label}
        </span>
      </summary>
      <div className="absolute end-0 z-30 mt-2 flex w-64 flex-col gap-1 rounded-2xl border border-border bg-background p-2 shadow-lg">
        <p className="px-2 pt-1 text-xs text-muted">{t("scope.hint")}</p>
        <button type="button" onClick={() => onChange(null)} aria-pressed={value === null} className="flex items-center justify-between rounded-lg px-2 py-1.5 text-start text-sm font-medium hover:bg-surface">
          {t("scope.all")}
          {value === null && <Check aria-hidden="true" className="size-4 text-primary" />}
        </button>
        <ul className="max-h-60 overflow-y-auto" aria-label={t("scope.branches")}>
          {branches.map((branch) => (
            <li key={branch.id}>
              <label className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-surface">
                <input type="checkbox" checked={value === null || value.includes(branch.id)} onChange={() => toggle(branch.id)} className="size-4 accent-[var(--primary)]" />
                <span className="truncate" dir="auto">
                  {branch.name}
                </span>
              </label>
            </li>
          ))}
        </ul>
        <button type="button" onClick={() => details.current?.removeAttribute("open")} className="btn-primary mt-1 px-3 py-1.5 text-sm">
          {t("scope.done")}
        </button>
      </div>
    </details>
  );
}
