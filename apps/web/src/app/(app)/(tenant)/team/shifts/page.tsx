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
import { minuteToTime } from "@/lib/coverage";
import { weekStartFor } from "@/lib/hours";
import { canManageSettings, canManageTeam } from "@/lib/permissions";
import { getBranches, getTenantFor } from "@/lib/tenant";

import { BranchRoster } from "./branch-roster";
import { CoverageBanner } from "./coverage-banner";
import { CoverageSettings } from "./coverage-settings";
import { EditFromUrl } from "./edit-from-url";
import { PlanningSettings } from "./planning-settings";
import { PublishBar } from "./publish-bar";
import { PublishSettings } from "./publish-settings";
import { SaveShiftsDefault } from "./save-default";
import { StationSettings } from "./station-settings";
import { Segmented } from "./segmented";
import { type BoardGap, type BoardPerson, type BoardShift, type BoardStation, type BoardTemplate, type Editing, ShiftBoard } from "./shift-board";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

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
      <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
        <BackLink href="/team" label={t("team.title")} />
        <PageHeader title={t("shifts.soloTitle")} description={t("shifts.soloSubtitle")} />
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
      </Container>
    );
  }

  const colorOf = new Map(branches.map((b, i) => [b.id, branchColor(i)]));
  const rhythm = new Map(planning.map((p) => [p.location_id, p]));
  // What the owner saved as the way the board opens; the address overrides it.
  const savedBranches = (tenant.shifts_default_branches ?? []).filter((id) => colorOf.has(id));
  const view: "people" | "branches" = query.view === "branches" || query.view === "people" ? query.view : (tenant.shifts_default_view ?? "people");
  const requested = ("b" in query ? String(query.b ?? "").split(",") : savedBranches).filter((id) => colorOf.has(id));
  // Without a saved range, the board opens on the rhythm of the first branch shown.
  const first = rhythm.get(requested[0] ?? branches[0]?.id);
  const range: Range = isRange(query.range) ? query.range : (tenant.shifts_default_range ?? rangeOfCadence(first?.cadence));
  const customDays = first?.cadence === "custom" ? (first.days ?? 14) : 14;
  const anchor = isDay(query.date) ? query.date : today;
  const win = windowOf(range, anchor, customDays);
  const days = Array.from({ length: win.days }, (_, i) => addDays(win.start, i));
  const limit = view === "branches" ? branchLimit(range) : branches.length;
  const shown = (requested.length ? requested : branches.map((b) => b.id)).slice(0, limit);
  const allShown = shown.length === branches.length;
  const branchFilter = allShown ? {} : { location_id: shown };
  const canEdit = canManageTeam(tenant);
  // Managers can check the gaps against what the team already sees, leaving drafts out.
  const roster: "plan" | "published" = canEdit && query.roster === "published" ? "published" : "plan";
  const [shifts, awayRanges, rawTemplates, rawStations, rawGaps, ruleSets, availability] = await Promise.all([
    api.GET("/shifts", { params: { ...scope, query: { start: win.start, days: win.days, ...branchFilter } } }).then(unwrap),
    api.GET("/shifts/time-off", { params: { ...scope, query: { start: win.start, days: win.days } } }).then(unwrap),
    api.GET("/shift-templates", { params: scope }).then(unwrap),
    api.GET("/stations", { params: scope }).then(unwrap),
    api.GET("/shifts/coverage", { params: { ...scope, query: { start: win.start, days: win.days, ...branchFilter, ...(roster === "published" ? { published_only: true } : {}) } } }).then(unwrap),
    canEdit
      ? Promise.all(branches.map(async (b) => ({ id: b.id, rules: (await api.GET("/locations/{location_id}/coverage-rules", { params: { ...scope, path: { location_id: b.id } } })).data?.rules ?? [] })))
      : Promise.resolve([]),
    canEdit ? api.GET("/shifts/availability", { params: scope }).then(unwrap) : Promise.resolve([]),
  ]);
  const availabilityOf = new Map(availability.map((a) => [a.user_id, a.windows]));
  const templates: BoardTemplate[] = rawTemplates.map((x) => ({ id: x.id, locationId: x.location_id, name: x.name, starts: x.starts.slice(0, 5), ends: x.ends.slice(0, 5), position: x.position ?? null }));
  const stations: BoardStation[] = rawStations.map((x) => ({ id: x.id, locationId: x.location_id, name: x.name }));
  const gaps: BoardGap[] = rawGaps.map((g) => ({ locationId: g.location_id, locationName: g.location_name, day: g.day, starts: minuteToTime(g.starts_minute), ends: minuteToTime(g.ends_minute), startMinute: g.starts_minute, endMinute: g.ends_minute, needed: g.needed, have: g.have, available: (g.available ?? []).map((c) => c.user_name) }));
  // Monday first, as the coverage rules count weekdays.
  const weekdays = Array.from({ length: 7 }, (_, i) => formatDay(addDays("2024-01-01", i), locale, { weekday: "long" }));

  const href = (changes: Record<string, string | undefined>) => {
    // "all" keeps every branch when the saved default is a narrower set.
    const next: Record<string, string | undefined> = { view, range, date: anchor, roster: roster === "published" ? roster : undefined, b: allShown ? (savedBranches.length ? "all" : undefined) : shown.join(","), ...changes };
    const params = new URLSearchParams(Object.entries(next).filter((e): e is [string, string] => Boolean(e[1])));
    return `/team/shifts?${params}`;
  };
  const people: BoardPerson[] = team.members.map((m) => ({
    id: m.user_id,
    name: m.full_name || m.email,
    title: m.job_title ?? m.custom_role_name ?? t(`roles.${m.role}`),
    avatar: avatarSrc(m.user_id, m.avatar_url),
    homeId: m.home_location_id ?? null,
    availability: availabilityOf.get(m.user_id) ?? null,
  }));
  // Each away day in the window as `userId:day` (a range is spread over the days it covers).
  const away: Record<string, string | null> = {};
  for (const r of awayRanges) {
    for (const day of days) if (day >= r.starts_on && day <= r.ends_on) away[`${r.user_id}:${day}`] = r.reason ?? null;
  }
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
    stationId: s.station_id ?? null,
    stationName: s.station_name ?? null,
    position: s.position ?? null,
    note: s.note ?? null,
    isCover: s.is_cover,
    homeName: s.home_location_name ?? null,
    warning: s.on_time_off ? "timeOff" : s.outside_availability ? "outsideAvailability" : s.outside_hours ? "outsideHours" : null,
    draft: !s.published,
  }));
  const drafts = boardShifts.filter((s) => s.draft).length;
  const publishTime = tenant.shifts_publish_time.slice(0, 5);
  const publishSummary = !tenant.shifts_publish_auto
    ? t("shifts.publish.summary.manual")
    : tenant.shifts_publish_cadence === "weekly"
      ? t("shifts.publish.summary.weekly", { day: weekdays[tenant.shifts_publish_weekday], time: publishTime })
      : tenant.shifts_publish_cadence === "monthly"
        ? t("shifts.publish.summary.monthly", { day: tenant.shifts_publish_day, time: publishTime })
        : t("shifts.publish.summary.daily", { time: publishTime });
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
          detail: s.draft ? t("shifts.publish.draft") : s.isCover ? t("shifts.coverFrom", { branch: s.homeName ?? "" }) : (s.stationName ?? s.position),
          color: s.color,
          laneId: s.locationId,
          branch: null,
          cancelled: false,
        };
      })
    : [];
  const existing = typeof query.edit === "string" ? boardShifts.find((s) => s.id === query.edit) : undefined;
  // `?add=<day>:<branch>[:<station>]`: a new shift at that branch (and room), for someone who works there if possible.
  const [addDay, addBranch, addStation] = typeof query.add === "string" ? query.add.split(":") : [];
  const adding = isDay(addDay) && colorOf.has(addBranch) ? { shift: null, userId: (people.find((p) => p.homeId === addBranch) ?? people[0]).id, day: addDay, locationId: addBranch, stationId: stations.some((x) => x.id === addStation && x.locationId === addBranch) ? addStation : undefined } : undefined;
  const editing: Editing | undefined = existing ? { shift: existing, userId: existing.userId, day: existing.day } : adding;
  const last = days[days.length - 1];
  const rangeLabel =
    range === "day"
      ? formatDay(win.start, locale, { weekday: "long", day: "numeric", month: "long", year: "numeric" })
      : range === "month"
        ? formatDay(win.start, locale, { month: "long", year: "numeric" })
        : `${formatDay(win.start, locale, { day: "numeric", month: "short" })} – ${formatDay(last, locale, { day: "numeric", month: "short", year: "numeric" })}`;
  const showToday = !days.includes(today);
  const sameSet = (a: string[], b: string[]) => a.length === b.length && a.every((id) => b.includes(id));
  const savedView = tenant.shifts_default_view ?? "people";
  const savedRange = tenant.shifts_default_range ?? rangeOfCadence(rhythm.get(savedBranches[0] ?? branches[0]?.id)?.cadence);
  const currentSet = allShown ? [] : shown;
  const showSave = canManageSettings(tenant) && (view !== savedView || range !== savedRange || !sameSet(currentSet, savedBranches));
  const branchList = branches.map((b) => ({ ...b, color: colorOf.get(b.id) ?? "" }));

  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-5 py-8 sm:py-10">
      <LiveRefresh />
      <BackLink href="/team" label={t("team.title")} />
      <PageHeader title={t("shifts.title")} />

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
            items={(["people", "branches"] as const).map((v) => ({ key: v, label: t(`shifts.views.${v}`), href: href({ view: v }), active: v === view }))}
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
                href={href({ b: nextIds.length === 0 || nextIds.length === branches.length ? (savedBranches.length ? "all" : undefined) : nextIds.join(",") })}
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

      {canEdit && <PublishBar key={`${win.start}-${win.days}-${drafts}`} drafts={drafts} start={win.start} days={win.days} branches={allShown ? [] : shown} summary={publishSummary} />}

      <CoverageBanner gaps={gaps} locale={locale} showBranch={branches.length > 1} roster={canEdit ? { current: roster, plan: href({ roster: undefined }), published: href({ roster: "published" }) } : undefined} />

      {showSave && <SaveShiftsDefault view={view} range={range} branches={currentSet} />}

      {gridView ? (
        <TimeGrid
          days={days}
          timeZone={tenant.time_zone}
          locale={locale}
          events={gridEvents}
          shifts={[]}
          gaps={gaps.map((g) => ({ laneId: g.locationId, day: g.day, start: g.startMinute, end: g.endMinute, label: `${g.locationName} ${g.starts}–${g.ends}: ${t("shifts.coverage.gap", { have: g.have, needed: g.needed })}` }))}
          lanes={branchList.filter((b) => shown.includes(b.id)).map((b) => ({ id: b.id, name: b.name, color: b.color }))}
          closed={{}}
          open={null}
          labels={{ now: t("schedule.now"), closed: t("schedule.closedDay"), shifts: t("shifts.title"), empty: t("shifts.nobody"), more: t.raw("schedule.more") as string, onShift: t("schedule.onShift"), peopleOnShift: t("shifts.peopleOnShift"), coverFrom: t.raw("shifts.coverFrom") as string, close: t("shifts.close") }}
          dayHref={range === "week" ? href({ range: "day", date: "__day__" }) : null}
        />
      ) : view === "branches" ? (
        <BranchRoster gaps={gaps} days={days} today={today} locale={locale} branches={branchList.filter((b) => shown.includes(b.id))} shifts={boardShifts} people={people} stations={stations} editHref={canEdit ? (id) => href({ edit: id }) : undefined} addHref={canEdit ? (day, branchId, stationId) => href({ add: `${day}:${branchId}${stationId ? `:${stationId}` : ""}` }) : undefined} />
      ) : (
        <ShiftBoard
          key={`${win.start}-${win.days}`}
          days={days}
          today={today}
          locale={locale}
          people={people}
          shifts={boardShifts}
          away={away}
          branches={branchList}
          canEdit={canEdit}
          copyMode={range === "week" ? "week" : range === "day" ? "day" : null}
          weekStart={win.start}
          compact={win.days > 7}
          templates={templates}
          stations={stations}
          gaps={gaps}
        />
      )}
      {editing && canEdit && <EditFromUrl key={`${editing.shift?.id ?? "new"}-${editing.day}-${editing.locationId ?? ""}`} editing={editing} people={people} branches={branchList} templates={templates} stations={stations} closeHref={href({ edit: undefined, add: undefined })} away={away} />}
      {canEdit && <StationSettings branches={branchList.map((b) => ({ id: b.id, name: b.name, color: b.color, stations: stations.filter((x) => x.locationId === b.id) }))} />}
      {canEdit && <CoverageSettings weekdays={weekdays} branches={branchList.map((b) => ({ id: b.id, name: b.name, color: b.color, rules: ruleSets.find((r) => r.id === b.id)?.rules ?? [] }))} />}
      {canManageSettings(tenant) && <PublishSettings auto={tenant.shifts_publish_auto} cadence={tenant.shifts_publish_cadence} weekday={tenant.shifts_publish_weekday} day={tenant.shifts_publish_day} time={publishTime} weekdays={weekdays} />}
      {canEdit && <PlanningSettings branches={branchList.map((b) => ({ id: b.id, name: b.name, color: b.color, cadence: rhythm.get(b.id)?.cadence ?? "weekly", days: rhythm.get(b.id)?.days ?? null }))} />}
    </Container>
  );
}
