"use client";

import { Building2, Check } from "lucide-react";
import { useTranslations } from "next-intl";
import { useId, useRef } from "react";

export type Branch = { id: string; name: string };

/** Which branches an agent looks at in this chat: the whole network, or only the ticked ones. The API still caps it to the branches the person may see. */
export function ScopePicker({ branches, value, onChange }: { branches: Branch[]; value: string[] | null; onChange: (ids: string[] | null) => void }) {
  const t = useTranslations("aiTeam");
  const trigger = useRef<HTMLButtonElement>(null);
  const popover = useRef<HTMLDivElement>(null);
  const id = useId();
  if (branches.length < 2) return null;
  const label = value === null ? t("scope.all") : value.length === 1 ? (branches.find((b) => b.id === value[0])?.name ?? t("scope.some", { count: 1 })) : t("scope.some", { count: value.length });
  const toggle = (id: string) => {
    const next = new Set(value ?? branches.map((b) => b.id));
    if (next.has(id)) next.delete(id);
    else next.add(id);
    // Nothing left ticked is not a scope: fall back to everything. All ticked is the same as everything.
    onChange(next.size === 0 || next.size === branches.length ? null : [...next]);
  };
  // The list lives in the browser's top layer, so a dialog's overflow can never clip it. It is placed under the button, or above when there is no room below.
  const place = () => {
    const box = trigger.current?.getBoundingClientRect();
    const el = popover.current;
    if (!box || !el) return;
    const height = el.offsetHeight;
    const below = window.innerHeight - box.bottom - 8;
    const top = below >= height || below >= box.top ? box.bottom + 8 : Math.max(8, box.top - height - 8);
    const rtl = getComputedStyle(el).direction === "rtl";
    const width = el.offsetWidth;
    const left = rtl ? box.left : box.right - width;
    el.style.top = `${top}px`;
    el.style.left = `${Math.min(Math.max(8, left), window.innerWidth - width - 8)}px`;
  };
  const close = () => popover.current?.hidePopover();
  return (
    <>
      <button ref={trigger} type="button" popoverTarget={id} className="btn-secondary inline-flex cursor-pointer items-center gap-2 px-3 py-1.5 text-sm" aria-label={t("scope.label")} aria-haspopup="true">
        <Building2 aria-hidden="true" className="size-4" />
        <span className="max-w-[10rem] truncate" dir="auto">
          {label}
        </span>
      </button>
      <div ref={popover} id={id} popover="auto" onToggle={(e) => (e as unknown as ToggleEvent).newState === "open" && place()} role="group" aria-label={t("scope.label")} className="scope-popover m-0 flex w-64 flex-col gap-1 rounded-2xl border border-border bg-background p-2 text-foreground shadow-lg">
        <p className="px-2 pt-1 text-xs text-muted">{t("scope.hint")}</p>
        <button type="button" onClick={() => onChange(null)} aria-pressed={value === null} className="btn-plain flex items-center justify-between rounded-lg px-2 py-1.5 text-start text-sm font-medium hover:bg-surface">
          {t("scope.all")}
          {value === null && <Check aria-hidden="true" className="size-4 text-primary-ink" />}
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
        <button type="button" onClick={close} className="btn-primary mt-1 px-3 py-1.5 text-sm">
          {t("scope.done")}
        </button>
      </div>
    </>
  );
}
