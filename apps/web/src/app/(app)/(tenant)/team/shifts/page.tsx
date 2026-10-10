import { CalendarCog, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Clock, MapPin } from "lucide-react";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { avatarSrc } from "@/components/avatar";
import { BackLink } from "@/components/back-link";
import { LiveRefresh } from "@/components/live-refresh";
import { OpeningHoursList } from "@/components/opening-hours";
import { unwrap } from "@/lib/api";
import { TimeGrid, type GridEvent } from "@/components/calendar-board/time-grid";
import { branchColor, minutesIn } from "@/lib/calendar";
import { addDays, dayOf, formatDay, formatTime, isDay, todayIn } from "@/lib/dates";
import { branchLimit, isRange, RANGES, type Range, rangeOfCadence, stepWindow, windowOf } from "@/lib/shift-window";
import { weekStartFor } from "@/lib/hours";
import { canManageTeam } from "@/lib/permissions";
import { getBranches, getTenantFor } from "@/lib/tenant";

import { BranchRoster } from "./branch-roster";
import { EditFromUrl } from "./edit-from-url";
import { PlanningSettings } from "./planning-settings";
import { Segmented } from "./segmented";
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
  const [team, branches, planning] = await Promise.all([
    api.GET("/staff", { params: scope }).then(unwrap),
    getBranches(),
    api.GET("/shifts/planning", { params: scope }).then(unwrap),
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
  const rhythm = new Map(planning.map((p) => [p.location_id, p]));
  const view: "people" | "branches" = query.view === "branches" ? "branches" : "people";
  const requested = String(query.b ?? "").split(",").filter((id) => colorOf.has(id));
  // The board opens on the rhythm of the first branch shown.
  const first = rhythm.get(requested[0] ?? branches[0]?.id);
  const range: Range = isRange(query.range) ? query.range : rangeOfCadence(first?.cadence);
  const customDays = first?.cadence === "custom" ? (first.days ?? 14) : 14;
  const anchor = isDay(query.date) ? query.date : today;
  const win = windowOf(range, anchor, customDays);
  const days = Array.from({ length: win.days }, (_, i) => addDays(win.start, i));
  const limit = view === "branches" ? branchLimit(range) : branches.length;
  const shown = (requested.length ? requested : branches.map((b) => b.id)).slice(0, limit);
  const allShown = shown.length === branches.length;
  const shifts = await api
    .GET("/shifts", { params: { ...scope, query: { start: win.start, days: win.days, ...(allShown ? {} : { location_id: shown }) } } })
    .then(unwrap);

  const href = (changes: Record<string, string | undefined>) => {
    const next: Record<string, string | undefined> = { view: view === "branches" ? "branches" : undefined, range, date: anchor, b: allShown ? undefined : shown.join(","), ...changes };
    const params = new URLSearchParams(Object.entries(next).filter((e): e is [string, string] => Boolean(e[1])));
    return `/team/shifts?${params}`;
  };
  const people: BoardPerson[] = team.members.map((m) => ({
    id: m.user_id,
    name: m.full_name || m.email,
    title: m.job_title ?? m.custom_role_name ?? t(`roles.${m.role}`),
    avatar: avatarSrc(m.user_id, m.avatar_url),
    homeId: m.home_location_id ?? null,
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
    isCover: s.is_cover,
    homeName: s.home_location_name ?? null,
    warning: s.on_time_off ? "timeOff" : s.outside_hours ? "outsideHours" : null,
  }));
  // Day and week "by branch": the shared time grid, one lane per branch, each shift a block.
  const gridView = view === "branches" && (range === "day" || range === "week") && shown.length > 1;
  const gridEvents: GridEvent[] = gridView
    ? boardShifts.map((s, i) => {
        const raw = shifts[i];
        const start = minutesIn(raw.starts_at, tenant.time_zone);
        const sameDay = dayOf(raw.ends_at, tenant.time_zone) === s.day;
        return {
          id: s.id,
          href: href({ edit: s.id }),
          day: s.day,
          start,
          end: sameDay ? minutesIn(raw.ends_at, tenant.time_zone) : 1440,
          time: `${s.starts}–${s.ends}`,
          title: people.find((p) => p.id === s.userId)?.name ?? "",
          detail: s.isCover ? t("shifts.coverFrom", { branch: s.homeName ?? "" }) : s.position,
          color: s.color,
          laneId: s.locationId,
          branch: null,
          cancelled: false,
        };
      })
    : [];
  const editing = typeof query.edit === "string" ? boardShifts.find((s) => s.id === query.edit) : undefined;
  const last = days[days.length - 1];
  const rangeLabel =
    range === "day"
      ? formatDay(win.start, locale, { weekday: "long", day: "numeric", month: "long", year: "numeric" })
      : range === "month"
        ? formatDay(win.start, locale, { month: "long", year: "numeric" })
        : `${formatDay(win.start, locale, { day: "numeric", month: "short" })} – ${formatDay(last, locale, { day: "numeric", month: "short", year: "numeric" })}`;
  const showToday = !days.includes(today);
  const canEdit = canManageTeam(tenant);
  const branchList = branches.map((b) => ({ ...b, color: colorOf.get(b.id) ?? "" }));

  return (
    <main className="enter flex w-full flex-1 flex-col gap-5 px-4 py-8 sm:px-6 sm:py-10">
      <LiveRefresh />
      <div className="flex flex-col gap-2">
        <BackLink href="/team" label={t("team.title")} />
        <h1 className="text-3xl font-bold">{t("shifts.title")}</h1>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <nav aria-label={t("shifts.navigate")} className="flex items-center gap-1.5">
          <Link href={href({ date: stepWindow(range, win, -1) })} aria-label={t(`shifts.previous.${range}`)} className="btn-secondary size-9">
            <ChevronsLeft aria-hidden="true" className="size-4 rtl:rotate-180" />
          </Link>
          {(range === "week" || range === "custom") && (
            <Link href={href({ date: addDays(anchor, -1) })} aria-label={t("shifts.previous.day")} className="btn-secondary size-9">
              <ChevronLeft aria-hidden="true" className="size-4 rtl:rotate-180" />
            </Link>
          )}
          <Link href={href({ date: today })} aria-current={showToday ? undefined : "date"} className={`${showToday ? "btn-secondary" : "btn-primary"} px-3 py-2 text-sm`}>
            {t("shifts.today")}
          </Link>
          {(range === "week" || range === "custom") && (
            <Link href={href({ date: addDays(anchor, 1) })} aria-label={t("shifts.next.day")} className="btn-secondary size-9">
              <ChevronRight aria-hidden="true" className="size-4 rtl:rotate-180" />
            </Link>
          )}
          <Link href={href({ date: stepWindow(range, win, 1) })} aria-label={t(`shifts.next.${range}`)} className="btn-secondary size-9">
            <ChevronsRight aria-hidden="true" className="size-4 rtl:rotate-180" />
          </Link>
          <span className="ms-2 text-lg font-semibold">{rangeLabel}</span>
        </nav>
        <div className="flex flex-wrap items-center gap-2">
          <Segmented
            label={t("shifts.rangeLabel")}
            items={RANGES.map((r) => ({ key: r, label: t(`shifts.ranges.${r}`), href: href({ range: r }), active: r === range }))}
          />
          <Segmented
            label={t("shifts.viewLabel")}
            items={(["people", "branches"] as const).map((v) => ({ key: v, label: t(`shifts.views.${v}`), href: href({ view: v === "branches" ? "branches" : undefined }), active: v === view }))}
          />
        </div>
      </div>

      {branches.length > 1 && (
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label={t("shifts.branchesShown")}>
          {branchList.map((b) => {
            const on = shown.includes(b.id);
            const next = on ? shown.filter((id) => id !== b.id) : [...shown, b.id];
            const nextIds = view === "branches" ? next.slice(-limit) : next;
            return (
              <Link
                key={b.id}
                href={href({ b: nextIds.length === 0 || nextIds.length === branches.length ? undefined : nextIds.join(",") })}
                aria-pressed={on}
                className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors ${on ? "border-transparent font-medium text-foreground" : "border-border text-muted hover:text-foreground"}`}
                style={on ? { background: `color-mix(in oklab, ${b.color} 16%, var(--surface))`, boxShadow: `inset 0 0 0 1.5px ${b.color}` } : undefined}
              >
                <span aria-hidden="true" className="size-2.5 rounded-full" style={{ background: b.color }} />
                <span dir="auto">{b.name}</span>
              </Link>
            );
          })}
          {view === "branches" && <span className="text-xs text-muted">{t("shifts.limitHint", { count: limit })}</span>}
        </div>
      )}

      {gridView ? (
        <TimeGrid
          days={days}
          timeZone={tenant.time_zone}
          locale={locale}
          events={gridEvents}
          shifts={[]}
          lanes={branchList.filter((b) => shown.includes(b.id)).map((b) => ({ id: b.id, name: b.name, color: b.color }))}
          closed={{}}
          open={null}
          labels={{ now: t("schedule.now"), closed: t("schedule.closedDay"), shifts: t("shifts.title"), empty: t("shifts.nobody"), more: t.raw("schedule.more") as string, onShift: t("schedule.onShift"), peopleOnShift: t("shifts.peopleOnShift"), coverFrom: t.raw("shifts.coverFrom") as string, close: t("shifts.close") }}
          dayHref={range === "week" ? href({ range: "day", date: "__day__" }) : null}
        />
      ) : view === "branches" ? (
        <BranchRoster days={days} today={today} locale={locale} branches={branchList.filter((b) => shown.includes(b.id))} shifts={boardShifts} people={people} />
      ) : (
        <ShiftBoard
          key={`${win.start}-${win.days}`}
          days={days}
          today={today}
          locale={locale}
          people={people}
          shifts={boardShifts}
          branches={branchList}
          canEdit={canEdit}
          canCopy={range === "week"}
          weekStart={win.start}
          compact={win.days > 7}
        />
      )}
      {editing && canEdit && <EditFromUrl shift={editing} people={people} branches={branchList} closeHref={href({ edit: undefined })} />}
      {canEdit && <PlanningSettings branches={branchList.map((b) => ({ id: b.id, name: b.name, color: b.color, cadence: rhythm.get(b.id)?.cadence ?? "weekly", days: rhythm.get(b.id)?.days ?? null }))} />}
    </main>
  );
}
