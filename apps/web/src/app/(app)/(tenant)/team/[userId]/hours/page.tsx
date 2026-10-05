import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { unwrap } from "@/lib/api";
import { formatDay, todayIn } from "@/lib/dates";
import { getTenantFor } from "@/lib/tenant";

import { removeTimeOff } from "./actions";
import { HoursForm } from "./hours-form";
import { TimeOffForm } from "./time-off";
import { isolate } from "@/lib/bidi";

export default async function StaffHoursPage({ params }: PageProps<"/team/[userId]/hours">) {
  const { userId } = await params;
  const t = await getTranslations();
  const { api, scope, tenant } = await getTenantFor("schedule.write");
  const team = unwrap(await api.GET("/staff", { params: scope }));
  const member = team.members.find((m) => m.user_id === userId);
  if (!member) notFound();
  const [hours, timeOff] = await Promise.all([
    api.GET("/staff/{user_id}/hours", { params: { ...scope, path: { user_id: userId } } }).then(unwrap),
    api.GET("/staff/{user_id}/time-off", { params: { ...scope, path: { user_id: userId } } }).then(unwrap),
  ]);
  const locale = await getLocale();
  const day = (value: string) => formatDay(value, locale, { weekday: "short", day: "numeric", month: "short" });
  // The week starts on Sunday in Israel and on Monday elsewhere (0 = Monday).
  const weekStartsOn = tenant.locale === "he" ? 6 : 0;

  return (
    <main className="enter mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/team" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("common.back")}
      </Link>
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold">{t("hours.title")}</h1>
        <p className="text-muted">
          {t("hours.subtitle", { name: isolate(member.full_name ?? member.email) })}
        </p>
      </div>
      <section className="card p-6">
        <HoursForm
          userId={userId}
          weekStartsOn={weekStartsOn}
          initial={hours.blocks.map((block) => ({ weekday: block.weekday, starts: block.starts.slice(0, 5), ends: block.ends.slice(0, 5) }))}
        />
      </section>

      <section aria-labelledby="time-off-heading" className="card flex flex-col gap-4 p-6">
        <div className="flex flex-col gap-1">
          <h2 id="time-off-heading" className="text-lg font-semibold">{t("timeOff.title")}</h2>
          <p className="text-sm text-muted">{t("timeOff.hint")}</p>
        </div>
        {timeOff.length > 0 && (
          <ul className="flex flex-col divide-y divide-border">
            {timeOff.map((entry) => (
              <li key={entry.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
                <span>
                  <span className="font-medium">
                    {entry.starts_on === entry.ends_on ? day(entry.starts_on) : `${day(entry.starts_on)} – ${day(entry.ends_on)}`}
                  </span>
                  {entry.reason && <span dir="auto" className="text-muted"> · {entry.reason}</span>}
                </span>
                <form action={removeTimeOff.bind(null, userId, entry.id)}>
                  <button type="submit" className="text-danger underline-offset-4 hover:underline">
                    {t("timeOff.remove")}
                  </button>
                </form>
              </li>
            ))}
          </ul>
        )}
        <TimeOffForm userId={userId} today={todayIn(tenant.time_zone)} />
      </section>
    </main>
  );
}
