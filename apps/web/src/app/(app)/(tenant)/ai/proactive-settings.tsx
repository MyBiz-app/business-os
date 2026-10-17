"use client";

import { Sunrise } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState, useTransition } from "react";

import { Field } from "@/components/form/field";

import { weekdayNames } from "./describe-schedule";
import { type ProactiveSetting, type ProactiveSettings, setProactive } from "./tasks-actions";

type Translate = ReturnType<typeof useTranslations<"aiTeam">>;

/** The proactive behaviours of the AI team: a morning briefing and weekly suggestions, off until switched on. */
export function ProactiveSettingsPanel({ settings, timeZone }: { settings: ProactiveSettings; timeZone: string }) {
  const t = useTranslations("aiTeam");
  return (
    <section aria-labelledby="proactive-title" className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 id="proactive-title" className="flex items-center gap-2 text-xl font-semibold">
          <Sunrise aria-hidden="true" className="size-5 text-primary-ink" />
          {t("tasks.proactive.title")}
        </h2>
        <p className="max-w-3xl text-sm text-muted">{t("tasks.proactive.subtitle")}</p>
      </div>
      <ul className="grid gap-3 md:grid-cols-2">
        {settings.settings.map((setting) => (
          <ProactiveRow key={setting.key} setting={setting} canManage={settings.can_manage} timeZone={timeZone} t={t} />
        ))}
      </ul>
    </section>
  );
}

function ProactiveRow({ setting, canManage, timeZone, t }: { setting: ProactiveSetting; canManage: boolean; timeZone: string; t: Translate }) {
  const locale = useLocale();
  const [pending, start] = useTransition();
  const [time, setTime] = useState(setting.time);
  const [weekday, setWeekday] = useState(setting.weekday ?? 6);
  const [message, setMessage] = useState<string | null>(null);
  const key = setting.key === "morning_briefing" ? "briefing" : "suggestions";
  const days = weekdayNames(locale);
  const changed = time !== setting.time || (setting.weekday !== null && weekday !== setting.weekday);
  const next = setting.next_run_at ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone }).format(new Date(setting.next_run_at)) : null;
  const reasonKey = `tasks.reason.${setting.paused_reason}` as "tasks.reason.cancelled";

  const save = (enabled: boolean) =>
    start(async () => {
      setMessage(null);
      const result = await setProactive(setting.key, { enabled, time, ...(setting.weekday !== null ? { weekday } : {}) });
      setMessage(result.ok ? t("tasks.proactive.saved") : t("tasks.proactive.failed"));
    });

  return (
    <li className="card flex flex-col gap-3 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex min-w-0 flex-col gap-1">
          <h3 className="font-semibold">{t(`tasks.proactive.${key}.name`)}</h3>
          <p className="text-sm text-muted">{t(`tasks.proactive.${key}.description`)}</p>
        </div>
        <span className={`text-sm font-medium ${setting.enabled ? "text-success-ink" : "text-muted"}`}>
          {setting.enabled ? (setting.weekday === null ? t("tasks.proactive.onAt", { time: setting.time }) : t("tasks.proactive.onWeekly", { day: days[setting.weekday], time: setting.time })) : t("tasks.proactive.off")}
        </span>
      </div>
      {canManage && (
        <div className="flex flex-wrap items-end gap-3">
          <Field label={t("tasks.proactive.time")} type="time" value={time} onChange={(e) => setTime(e.target.value)} />
          {setting.weekday !== null && (
            <label className="flex flex-col gap-1.5 text-sm font-medium">
              {t("tasks.proactive.weekday")}
              <select className="control px-3 py-2" value={weekday} onChange={(e) => setWeekday(Number(e.target.value))}>
                {days.map((name, index) => (
                  <option key={name} value={index}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {setting.enabled ? (
            <>
              {changed && (
                <button type="button" disabled={pending || !time} onClick={() => save(true)} className="btn-primary px-3 py-2 text-sm">
                  {t("tasks.proactive.save")}
                </button>
              )}
              <button type="button" disabled={pending} onClick={() => save(false)} className="btn-secondary px-3 py-2 text-sm">
                {t("tasks.proactive.disable")}
              </button>
            </>
          ) : (
            <button type="button" disabled={pending || !time} onClick={() => save(true)} className="btn-primary px-3 py-2 text-sm">
              {t("tasks.proactive.enable")}
            </button>
          )}
        </div>
      )}
      {!canManage && <p className="text-sm text-muted">{t("tasks.proactive.managersOnly")}</p>}
      {setting.enabled && next && <p className="text-sm text-muted">{t("tasks.proactive.next", { when: next })}</p>}
      {!setting.enabled && setting.paused_reason && t.has(reasonKey) && <p className="text-sm text-danger">{t(reasonKey)}</p>}
      {canManage && <p className="text-xs text-muted">{t("tasks.proactive.cost", { credits: key === "briefing" ? 10 : 15 })}</p>}
      {message && (
        <p role="status" className="text-sm text-muted">
          {message}
        </p>
      )}
    </li>
  );
}
