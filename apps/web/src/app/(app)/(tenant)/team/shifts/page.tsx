import { CalendarCog, ChevronLeft, ChevronRight, Clock, MapPin } from "lucide-react";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { avatarSrc } from "@/components/avatar";
import { BackLink } from "@/components/back-link";
import { LiveRefresh } from "@/components/live-refresh";
import { OpeningHoursList } from "@/components/opening-hours";
import { unwrap } from "@/lib/api";
import { branchColor } from "@/lib/calendar";
import { addDays, dayOf, formatDay, formatTime, isDay, todayIn, weekStart } from "@/lib/dates";
import { weekStartFor } from "@/lib/hours";
import { canManageTeam } from "@/lib/permissions";
import { getBranches, getTenantFor } from "@/lib/tenant";

import { type BoardPerson, type BoardShift, ShiftBoard } from "./shift-board";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("shifts");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** Who works when and where, a week at a time. A business of one sees its opening hours and
 * availability instead: there is no one else to schedule. */
export default async function ShiftsPage({ searchParams }: PageProps<"/team/shifts">) {
  const t = await getTranslations();
  const locale = await getLocale();
  const { me, tenant, api, scope } = await getTenantFor("staff.read");
  const query = await searchParams;
  const today = todayIn(tenant.time_zone);
  const start = weekStart(isDay(query.week) ? query.week : today);
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));
  const [team, shifts, branches] = await Promise.all([
    api.GET("/staff", { params: scope }).then(unwrap),
    api.GET("/shifts", { params: { ...scope, query: { start, days: 7 } } }).then(unwrap),
    getBranches(),
  ]);

  if (team.members.length <= 1) {
    const hours = await Promise.all(
      branches.map(async (b) => ({ branch: b, hours: (await api.GET("/locations/{location_id}/hours", { params: { ...scope, path: { location_id: b.id } } })).data?.intervals ?? [] })),
    );
    return (
      <main className="enter mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-8 sm:px-6 sm:py-10">
        <div className="flex flex-col gap-2">
          <BackLink href="/team" label={t("team.title")} />
          <h1 className="text-3xl font-bold">{t("shifts.soloTitle")}</h1>
          <p className="text-sm text-muted">{t("shifts.soloSubtitle")}</p>
        </div>
        {hours.map(({ branch, hours }) => (
          <section key={branch.id} className="card flex flex-col gap-4 p-6">
            <div className="flex items-center justify-between gap-3">
              <h2 className="flex items-center gap-2 font-semibold">
                <MapPin aria-hidden="true" className="size-4 text-primary" />
                {t("openingHours.title")} · <span dir="auto">{branch.name}</span>
              </h2>
              <Link href={`/locations/${branch.id}`} className="btn-secondary px-3 py-1.5 text-sm">
                {t("common.edit")}
              </Link>
            </div>
            <OpeningHoursList hours={hours} weekStartsOn={weekStartFor(tenant.locale)} />
          </section>
        ))}
        <div className="grid gap-4 sm:grid-cols-2">
          <Link href={`/team/${me.id}/hours`} className="card card-hover flex items-center gap-3 p-5">
            <Clock aria-hidden="true" className="size-5 text-primary" />
            <span className="flex flex-col">
              <span className="font-semibold">{t("shifts.soloAvailability")}</span>
              <span className="text-sm text-muted">{t("shifts.soloAvailabilityHint")}</span>
            </span>
          </Link>
          <Link href="/schedule/closed" className="card card-hover flex items-center gap-3 p-5">
            <CalendarCog aria-hidden="true" className="size-5 text-primary" />
            <span className="flex flex-col">
              <span className="font-semibold">{t("schedule.closedDays")}</span>
              <span className="text-sm text-muted">{t("shifts.soloClosedHint")}</span>
            </span>
          </Link>
        </div>
      </main>
    );
  }

  const colorOf = new Map(branches.map((b, i) => [b.id, branchColor(i)]));
  const people: BoardPerson[] = team.members.map((m) => ({
    id: m.user_id,
    name: m.full_name || m.email,
    title: m.job_title ?? m.custom_role_name ?? t(`roles.${m.role}`),
    avatar: avatarSrc(m.user_id, m.avatar_url),
  }));
  const boardShifts: BoardShift[] = shifts.map((s) => ({
    id: s.id,
    userId: s.user_id,
    day: dayOf(s.starts_at, tenant.time_zone),
    starts: formatTime(s.starts_at, "en-GB", tenant.time_zone),
    ends: formatTime(s.ends_at, "en-GB", tenant.time_zone),
    minutes: Math.round((Date.parse(s.ends_at) - Date.parse(s.starts_at)) / 60000),
    locationId: s.location_id,
    locationName: s.location_name,
    color: colorOf.get(s.location_id) ?? "var(--primary)",
    position: s.position ?? null,
    note: s.note ?? null,
    warning: s.on_time_off ? "timeOff" : s.outside_hours ? "outsideHours" : null,
  }));
  const range = `${formatDay(days[0], locale, { day: "numeric", month: "short" })} – ${formatDay(days[6], locale, { day: "numeric", month: "short", year: "numeric" })}`;

  return (
    <main className="enter flex w-full flex-1 flex-col gap-6 px-4 py-8 sm:px-6 sm:py-10">
      <LiveRefresh />
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-2">
          <BackLink href="/team" label={t("team.title")} />
          <h1 className="text-3xl font-bold">{t("shifts.title")}</h1>
          <p className="text-sm text-muted">{range}</p>
        </div>
        <nav aria-label={t("shifts.title")} className="flex items-center gap-1.5">
          <Link href={`/team/shifts?week=${addDays(start, -7)}`} aria-label={t("schedule.previousWeek")} className="btn-secondary size-9">
            <ChevronLeft aria-hidden="true" className="size-4 rtl:rotate-180" />
          </Link>
          <Link href="/team/shifts" className="btn-secondary px-3 py-2 text-sm">
            {t("schedule.thisWeek")}
          </Link>
          <Link href={`/team/shifts?week=${addDays(start, 7)}`} aria-label={t("schedule.nextWeek")} className="btn-secondary size-9">
            <ChevronRight aria-hidden="true" className="size-4 rtl:rotate-180" />
          </Link>
        </nav>
      </div>
      <ShiftBoard
        key={start}
        days={days}
        today={today}
        locale={locale}
        people={people}
        shifts={boardShifts}
        branches={branches.map((b) => ({ ...b, color: colorOf.get(b.id) ?? "" }))}
        canEdit={canManageTeam(tenant)}
        weekStart={start}
      />
    </main>
  );
}
