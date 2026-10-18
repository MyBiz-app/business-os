import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/empty-state";
import { unwrap } from "@/lib/api";
import { dayOf, formatDay, formatTime, isDay } from "@/lib/dates";
import { getBranches, getTenantFor } from "@/lib/tenant";

import { EntryActions } from "./entry-actions";

const MODES = ["auto", "first_come", "manual"] as const;
const hhmm = (time: string | null | undefined) => (time ?? "").slice(0, 5);

/** The waitlists (R30): everyone waiting for a class, an appointment or a court, by day, with what
 * the team can do about it. In the manual mode this is where the team decides who is let in. */
export default async function WaitlistPage({ searchParams }: PageProps<"/schedule/waitlist">) {
  const t = await getTranslations("waitlist");
  const tSchedule = await getTranslations("schedule");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("schedule.read");
  const query = await searchParams;
  const one = (value: string | string[] | undefined) => (typeof value === "string" && value !== "" ? value : undefined);
  const day = isDay(query.day) ? query.day : undefined;
  const mode = MODES.find((m) => m === query.mode);
  const [entries, services, branches] = await Promise.all([
    api.GET("/waitlist", { params: { ...scope, query: { day, mode, service_id: one(query.service), location_id: one(query.branch) } } }).then(unwrap),
    api.GET("/services", { params: { ...scope, query: { active: true } } }).then((r) => r.data ?? []),
    getBranches(),
  ]);
  const canManage = tenant.permissions.includes("bookings.manage");

  const when = (entry: (typeof entries)[number]) => {
    if (entry.kind === "range") return t("kinds.range", { from: hhmm(entry.from_time), to: hhmm(entry.to_time) });
    if (entry.kind === "day") return t("kinds.day");
    if (entry.starts_at) return t(entry.kind === "session" ? "kinds.session" : "kinds.slot", { time: formatTime(entry.starts_at, locale, tenant.time_zone) });
    return "";
  };

  return (
    <Container as="main" size="wide" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <Link href="/schedule" className="text-sm text-primary-ink underline-offset-4 hover:underline">
        {tSchedule("back")}
      </Link>
      <PageHeader title={t("title")} description={t("subtitle")} />

      <form method="get" className="card flex flex-wrap items-end gap-3 p-4" aria-label={t("filters.label")}>
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("filters.day")}
          <input type="date" name="day" defaultValue={day} className="control px-3 py-2" />
        </label>
        {branches.length > 1 && (
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            {t("filters.branch")}
            <select name="branch" defaultValue={one(query.branch) ?? ""} className="control px-3 py-2">
              <option value="">{t("filters.allBranches")}</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("filters.service")}
          <select name="service" defaultValue={one(query.service) ?? ""} className="control px-3 py-2">
            <option value="">{t("filters.allServices")}</option>
            {services.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("filters.mode")}
          <select name="mode" defaultValue={mode ?? ""} className="control px-3 py-2">
            <option value="">{t("filters.allModes")}</option>
            {MODES.map((m) => (
              <option key={m} value={m}>
                {t(`modes.${m}`)}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="btn-secondary px-4 py-2.5 text-sm">
          {t("filters.apply")}
        </button>
        {(day || mode || query.service || query.branch) && (
          <Link href="/schedule/waitlist" className="text-sm text-primary-ink underline-offset-4 hover:underline">
            {t("filters.clear")}
          </Link>
        )}
      </form>

      {entries.length === 0 ? (
        <EmptyState variant="calendar">{t("empty")}</EmptyState>
      ) : (
        <ul className="flex flex-col gap-3">
          {entries.map((entry) => {
            const open = entry.open_session_id !== null && entry.open_session_id !== undefined;
            return (
              <li key={`${entry.source}-${entry.id}`} className="card flex flex-wrap items-center justify-between gap-4 p-4">
                <div className="flex min-w-0 flex-col gap-1">
                  <p className="flex flex-wrap items-baseline gap-x-2">
                    <Link href={`/clients/${entry.client_id}`} dir="auto" className="font-semibold underline-offset-4 hover:underline">
                      {entry.client_name}
                    </Link>
                    <span className="text-sm text-muted">#{entry.position}</span>
                  </p>
                  <p dir="auto" className="text-sm">
                    {entry.service_name} · {formatDay(entry.day, locale, { weekday: "long", day: "numeric", month: "long" })} · {when(entry)}
                    {entry.staff_name && ` · ${entry.staff_name}`}
                    {entry.location_name && ` · ${entry.location_name}`}
                  </p>
                  <p className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="rounded-full bg-primary/12 px-2 py-0.5 font-semibold text-primary-ink">{t(`modes.${entry.mode}`)}</span>
                    {entry.status === "offered" && <span className="rounded-full bg-warning/15 px-2 py-0.5 font-semibold">{t("told")}</span>}
                    {open && entry.open_starts_at && (
                      <span className="rounded-full bg-success/15 px-2 py-0.5 font-semibold">
                        {t("openSpot", { when: `${formatDay(dayOf(entry.open_starts_at, tenant.time_zone), locale, { weekday: "short", day: "numeric", month: "short" })} ${formatTime(entry.open_starts_at, locale, tenant.time_zone)}` })}
                      </span>
                    )}
                  </p>
                </div>
                {canManage && (
                  <EntryActions
                    source={entry.source}
                    id={entry.id}
                    name={entry.client_name}
                    canAdmit={open}
                    canNotify={open && entry.source === "request" && entry.mode !== "off"}
                  />
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Container>
  );
}
