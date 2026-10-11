import { Clock } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { unwrap } from "@/lib/api";
import { addDays, todayIn } from "@/lib/dates";
import { getTenantFor } from "@/lib/tenant";

/** My time (#45): what I logged in the last 30 days, by day, with the week's and month's totals. */
export default async function MyTimePage() {
  const t = await getTranslations("time");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("clients.read");
  const today = todayIn(tenant.time_zone);
  const entries = unwrap(await api.GET("/time", { params: { ...scope, query: { mine: true, from: addDays(today, -30), to: today } } }));
  const hours = (minutes: number) => new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(minutes / 60);
  const sum = (from: string) => entries.filter((e) => e.day >= from).reduce((total, e) => total + e.minutes, 0);
  const byDay = new Map<string, typeof entries>();
  for (const entry of entries) byDay.set(entry.day, [...(byDay.get(entry.day) ?? []), entry]);
  const dayLabel = (day: string) => new Intl.DateTimeFormat(locale, { weekday: "long", day: "numeric", month: "long" }).format(new Date(`${day}T12:00:00`));

  return (
    <main className="enter mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex flex-col gap-1">
        <h1 className="flex items-center gap-2 text-3xl font-bold">
          <Clock aria-hidden="true" className="size-7 text-primary" />
          {t("myTitle")}
        </h1>
        <p className="text-sm text-muted">{t("mySubtitle")}</p>
      </div>
      <ul className="grid gap-3 sm:grid-cols-3">
        {[
          { label: t("today"), value: sum(today) },
          { label: t("last7"), value: sum(addDays(today, -6)) },
          { label: t("last30"), value: sum(addDays(today, -30)) },
        ].map((stat) => (
          <li key={stat.label} className="flex flex-col rounded-2xl border border-border bg-surface px-4 py-3">
            <span className="text-xs text-muted">{stat.label}</span>
            <span className="text-2xl font-bold tabular-nums">{t("hoursShort", { hours: hours(stat.value) })}</span>
          </li>
        ))}
      </ul>
      {entries.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border p-10 text-center text-muted">{t("myNone")}</p>
      ) : (
        [...byDay.entries()].map(([day, items]) => (
          <section key={day} aria-label={dayLabel(day)} className="card flex flex-col gap-2 p-5">
            <h2 className="flex justify-between font-semibold">
              <span>{dayLabel(day)}</span>
              <span className="tabular-nums">{t("hoursShort", { hours: hours(items.reduce((s, e) => s + e.minutes, 0)) })}</span>
            </h2>
            <ul className="flex flex-col divide-y divide-border text-sm">
              {items.map((entry) => (
                <li key={entry.id} className="flex justify-between gap-3 py-2">
                  <span className="min-w-0">
                    <Link href={`/clients/${entry.client_id}`} className="font-medium underline-offset-4 hover:underline" dir="auto">{entry.client_name}</Link>
                    <span dir="auto" className="text-muted"> · {entry.description}</span>
                  </span>
                  <span className="tabular-nums">{t("hoursShort", { hours: hours(entry.minutes) })}</span>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </main>
  );
}
