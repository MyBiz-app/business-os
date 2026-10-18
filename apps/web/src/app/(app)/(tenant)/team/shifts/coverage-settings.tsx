"use client";

import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { Plus, ShieldCheck, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState, useTransition } from "react";

import { endInputValue, minuteToTime, timeToMinute } from "@/lib/coverage";

import { type CoverageRuleInput, type CoverageState, saveCoverageRules } from "./actions";
import { ToastOnChange } from "@/components/toast/toaster";

type Branch = { id: string; name: string; color: string; rules: CoverageRuleInput[] };
type Row = { weekday: number; starts: string; ends: string; min: number };

const toRows = (rules: CoverageRuleInput[]): Row[] => rules.map((r) => ({ weekday: r.weekday, starts: minuteToTime(r.starts_minute), ends: endInputValue(r.ends_minute), min: r.min_staff }));

/** The least people each branch needs on shift, per weekday and stretch of the day. The shifts
 * board flags what falls short. `weekdays` lists the names Monday first. */
export function CoverageSettings({ branches, weekdays }: { branches: Branch[]; weekdays: string[] }) {
  const t = useTranslations("shifts");
  return (
    <CollapsibleSection
      icon={<ShieldCheck aria-hidden="true" className="size-4 text-primary-ink" />}
      title={t("coverage.title")}
      description={t("coverage.hint")}
      storageKey="shifts-coverage"
    >
      <ul className="-mx-5 -my-5 flex flex-col divide-y divide-border">
        {branches.map((branch) => (
          <CoverageBranch key={branch.id} branch={branch} weekdays={weekdays} />
        ))}
      </ul>
    </CollapsibleSection>
  );
}

function CoverageBranch({ branch, weekdays }: { branch: Branch; weekdays: string[] }) {
  const t = useTranslations("shifts");
  const [rows, setRows] = useState<Row[]>(() => toRows(branch.rules));
  const [state, setState] = useState<CoverageState>({});
  const [saving, start] = useTransition();
  const change = (index: number, patch: Partial<Row>) => setRows((all) => all.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  const save = () =>
    start(async () => {
      const rules = rows.map((r) => ({ weekday: r.weekday, starts_minute: timeToMinute(r.starts), ends_minute: timeToMinute(r.ends, true), min_staff: r.min }));
      setState(await saveCoverageRules(branch.id, rules));
    });
  return (
    <li className="flex flex-col gap-3 px-5 py-4">
      <span className="flex items-center gap-2 font-medium">
        <span aria-hidden="true" className="size-2.5 rounded-full" style={{ background: branch.color }} />
        <span dir="auto">{branch.name}</span>
      </span>
      {rows.length === 0 && <p className="text-sm text-muted">{t("coverage.none")}</p>}
      {rows.map((row, index) => (
        <div key={index} className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-muted">
            {t("coverage.day")}
            <select value={row.weekday} onChange={(e) => change(index, { weekday: Number(e.target.value) })} className="control px-2 py-1.5 text-sm text-foreground">
              {weekdays.map((name, i) => (
                <option key={i} value={i}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted">
            {t("starts")}
            <input type="time" value={row.starts} onChange={(e) => change(index, { starts: e.target.value })} required dir="ltr" className="control px-2 py-1.5 text-sm text-foreground" />
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted">
            {t("ends")}
            <input type="time" value={row.ends} onChange={(e) => change(index, { ends: e.target.value })} required dir="ltr" className="control px-2 py-1.5 text-sm text-foreground" />
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted">
            {t("coverage.min")}
            <input type="number" min={1} max={50} value={row.min} onChange={(e) => change(index, { min: Number(e.target.value) })} required dir="ltr" className="control w-20 px-2 py-1.5 text-sm text-foreground" />
          </label>
          <button type="button" onClick={() => setRows((all) => all.filter((_, i) => i !== index))} aria-label={t("coverage.remove")} className="btn-ghost size-9">
            <Trash2 aria-hidden="true" className="size-4" />
          </button>
        </div>
      ))}
      <p className="text-xs text-muted">{t("coverage.endHint")}</p>
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={() => setRows((all) => [...all, { weekday: 0, starts: "09:00", ends: "17:00", min: 1 }])} className="btn-secondary px-3 py-1.5 text-sm">
          <Plus aria-hidden="true" className="size-4" />
          {t("coverage.add")}
        </button>
        <button type="button" onClick={save} disabled={saving} aria-busy={saving} className="btn-primary px-3 py-1.5 text-sm">
          {t("planning.save")}
        </button>
        <ToastOnChange
          source={state}
          tone={state.saved ? "success" : "error"}
          message={state.saved ? t("planning.saved") : state.error ? t("errors.invalid") : undefined}
        />
      </div>
    </li>
  );
}
