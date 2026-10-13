"use client";

import { Send } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState, useState } from "react";

import { SubmitButton } from "@/components/form/submit-button";

import { type PublishingState, savePublishing } from "./actions";
import { FormError, FormNotice } from "@/components/form/form-message";

type Cadence = "daily" | "weekly" | "monthly";
type Props = { auto: boolean; cadence: Cadence; weekday: number; day: number; time: string; weekdays: string[] };

/** The owner decides when the roster goes out to the team: on a schedule or only by hand. */
export function PublishSettings({ auto, cadence: initial, weekday, day, time, weekdays }: Props) {
  const t = useTranslations("shifts.publish");
  const [state, action] = useActionState<PublishingState, FormData>(savePublishing, {});
  const [cadence, setCadence] = useState(initial);
  const [on, setOn] = useState(auto);
  // Sunday first, the way the week starts at the businesses this was built for.
  const order = [6, 0, 1, 2, 3, 4, 5];

  return (
    <details className="card group p-0">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-5 py-3 font-medium [&::-webkit-details-marker]:hidden">
        <Send aria-hidden="true" className="size-4 text-primary rtl:-scale-x-100" />
        {t("title")}
        <span className="ms-2 text-sm font-normal text-muted">{t("hint")}</span>
      </summary>
      <form action={action} className="flex flex-wrap items-center gap-3 border-t border-border px-5 py-3">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" name="auto" checked={on} onChange={(e) => setOn(e.target.checked)} className="size-4" />
          {t("auto")}
        </label>
        {on && (
          <>
            <label className="flex items-center gap-2 text-sm">
              <span className="text-muted">{t("cadence")}</span>
              <select name="cadence" value={cadence} onChange={(e) => setCadence(e.target.value as Cadence)} className="control px-2 py-1.5">
                {(["daily", "weekly", "monthly"] as const).map((c) => (
                  <option key={c} value={c}>
                    {t(`cadences.${c}`)}
                  </option>
                ))}
              </select>
            </label>
            {cadence === "weekly" && (
              <label className="flex items-center gap-2 text-sm">
                <span className="text-muted">{t("weekday")}</span>
                <select name="weekday" defaultValue={weekday} className="control px-2 py-1.5">
                  {order.map((d) => (
                    <option key={d} value={d}>
                      {weekdays[d]}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {cadence === "monthly" && (
              <label className="flex items-center gap-2 text-sm">
                <span className="text-muted">{t("dayOfMonth")}</span>
                <input name="day" type="number" min={1} max={28} defaultValue={day} required dir="ltr" className="control w-20 px-2 py-1.5" />
              </label>
            )}
            <label className="flex items-center gap-2 text-sm">
              <span className="text-muted">{t("time")}</span>
              <input name="time" type="time" defaultValue={time.slice(0, 5)} required dir="ltr" className="control px-2 py-1.5" />
            </label>
          </>
        )}
        {/* The hidden values keep what was set when the schedule is switched off. */}
        {!on && (
          <>
            <input type="hidden" name="cadence" value={cadence} />
            <input type="hidden" name="weekday" value={weekday} />
            <input type="hidden" name="day" value={day} />
            <input type="hidden" name="time" value={time.slice(0, 5)} />
          </>
        )}
        <SubmitButton className="px-3 py-1.5 text-sm">{t("save")}</SubmitButton>
        <FormNotice message={state.saved ? t("saved") : undefined} />
        <FormError toastOnly message={state.error ? t("saveError") : undefined} />
      </form>
      <p className="border-t border-border px-5 py-2 text-xs text-muted">{t("explain")}</p>
    </details>
  );
}
