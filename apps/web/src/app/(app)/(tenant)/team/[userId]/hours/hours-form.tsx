"use client";

import { Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState, useTransition } from "react";

import { FormError, FormNotice } from "@/components/form/form-message";

import { type Block, type HoursState, saveHours } from "./actions";

/** Weekly working hours: zero or more time ranges per weekday (0 = Monday). Days are listed
 * from the business's first day of the week (Sunday in Israel). */
export function HoursForm({ userId, initial, weekStartsOn }: { userId: string; initial: Block[]; weekStartsOn: number }) {
  const t = useTranslations("hours");
  const names = t.raw("weekdays") as string[];
  const [blocks, setBlocks] = useState<Block[]>(initial);
  const [state, setState] = useState<HoursState>({});
  const [pending, startTransition] = useTransition();
  const days = Array.from({ length: 7 }, (_, i) => (weekStartsOn + i) % 7);

  const update = (index: number, change: Partial<Block>) =>
    setBlocks((current) => current.map((block, i) => (i === index ? { ...block, ...change } : block)));

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        startTransition(async () => setState(await saveHours(userId, blocks)));
      }}
      className="flex flex-col gap-4"
    >
      <FormError message={state.error && t(`errors.${state.error}`)} />
      <FormNotice message={state.saved ? t("saved") : undefined} />
      <ul className="flex flex-col divide-y divide-border">
        {days.map((day) => {
          const mine = blocks.map((block, index) => ({ block, index })).filter(({ block }) => block.weekday === day);
          return (
            <li key={day} className="flex flex-wrap items-start gap-3 py-3">
              <span className="w-20 pt-2 font-semibold">{names[day]}</span>
              <div className="flex flex-1 flex-col gap-2">
                {mine.length === 0 && <span className="pt-2 text-sm text-muted">{t("none")}</span>}
                {mine.map(({ block, index }) => (
                  <div key={index} className="flex flex-wrap items-center gap-2">
                    <label className="flex items-center gap-2 text-sm">
                      <span className="sr-only">{`${names[day]} – ${t("from")}`}</span>
                      <input
                        type="time"
                        step={900}
                        value={block.starts}
                        onChange={(event) => update(index, { starts: event.target.value })}
                        className="control px-2 py-1.5"
                        dir="ltr"
                      />
                    </label>
                    <span aria-hidden="true">–</span>
                    <label className="flex items-center gap-2 text-sm">
                      <span className="sr-only">{`${names[day]} – ${t("to")}`}</span>
                      <input
                        type="time"
                        step={900}
                        value={block.ends}
                        onChange={(event) => update(index, { ends: event.target.value })}
                        className="control px-2 py-1.5"
                        dir="ltr"
                      />
                    </label>
                    <button
                      type="button"
                      aria-label={`${t("remove")} – ${names[day]} ${block.starts}–${block.ends}`}
                      onClick={() => setBlocks((current) => current.filter((_, i) => i !== index))}
                      className="flex size-9 items-center justify-center rounded-lg text-muted hover:bg-danger/10 hover:text-danger"
                    >
                      <Trash2 aria-hidden="true" className="size-4" />
                    </button>
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={() => setBlocks((current) => [...current, { weekday: day, starts: "09:00", ends: "17:00" }])}
                className="btn-secondary px-3 py-1.5 text-sm"
                aria-label={`${t("addBlock")} – ${names[day]}`}
              >
                <Plus aria-hidden="true" className="size-4" />
                {t("addBlock")}
              </button>
            </li>
          );
        })}
      </ul>
      <div>
        <button type="submit" disabled={pending} aria-busy={pending} className="btn-primary px-4 py-2.5">
          {t("save")}
        </button>
      </div>
    </form>
  );
}
