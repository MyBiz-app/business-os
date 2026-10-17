import { dayOf, formatTime, monthStart, todayIn } from "@business-os/i18n/dates";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { PermissionList } from "@/components/permission-list";
import { HoursForm } from "@/components/form/hours-form";
import { unwrap } from "@/lib/api";
import { isolate } from "@/lib/bidi";
import { formatDay } from "@/lib/dates";
import { toBlocks, weekStartFor } from "@/lib/hours";
import { hm } from "@/lib/time-clock";
import { getBranches, getTenant } from "@/lib/tenant";
import { canManagePayroll } from "@/lib/permissions";

import { PayrollFile } from "./payroll/payroll-file";
import { saveAvailability } from "./availability/actions";
import { removeTimeOff, saveHours } from "./hours/actions";
import { TimeOffForm } from "./hours/time-off";

type Context = Awaited<ReturnType<typeof getTenant>>;
type Member = { user_id: string; email: string; full_name: string | null; role: string; custom_role_id: string | null; custom_role_name: string | null; location_ids: string[]; home_location_id: string | null; joined_at: string; job_title: string | null; phone: string | null; permissions: string[] };

const UPCOMING_DAYS = 14;

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="card flex flex-col gap-3 p-6">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

/** Contact, branches, the next shifts and classes, and this month's hours. Hours need the
 * time-clock permission, so they simply do not show for anyone without it. */
export async function OverviewTab({ member, context }: { member: Member; context: Context }) {
  const t = await getTranslations("staffCard");
  const tAll = await getTranslations();
  const locale = await getLocale();
  const { api, scope, tenant } = context;
  const zone = tenant.time_zone;
  const today = todayIn(zone);
  const month = monthStart(today).slice(0, 7);
  const branches = await getBranches();
  const [shifts, sessions, clock] = await Promise.all([
    api.GET("/shifts", { params: { ...scope, query: { start: today, days: UPCOMING_DAYS, user_id: member.user_id } } }).then((r) => r.data ?? []),
    api.GET("/sessions", { params: { ...scope, query: { start: today, days: UPCOMING_DAYS } } }).then((r) => r.data ?? []),
    tenant.permissions.includes("time.approve")
      ? api.GET("/time-clock/people/{user_id}", { params: { ...scope, path: { user_id: member.user_id }, query: { month } } }).then((r) => r.data ?? null)
      : Promise.resolve(null),
  ]);
  const taught = sessions.filter((session) => session.instructor_user_id === member.user_id && session.status !== "cancelled");
  const names = branches.filter((branch) => member.location_ids.includes(branch.id)).map((branch) => branch.name);
  const day = (iso: string) => formatDay(dayOf(iso, zone), locale, { weekday: "short", day: "numeric", month: "short" });
  const span = (start: string, end: string) => `${formatTime(start, locale, zone)}-${formatTime(end, locale, zone)}`;
  const joined = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: zone }).format(new Date(member.joined_at));
  const facts: [string, React.ReactNode][] = [
    [t("role"), member.custom_role_name ?? tAll(`roles.${member.role}` as "roles.staff")],
    [t("branches"), names.length > 0 ? names.join(", ") : t("allBranches")],
    [t("email"), <bdi key="email" dir="ltr">{member.email}</bdi>],
    ...(member.phone ? ([[t("phone"), <bdi key="phone" dir="ltr">{member.phone}</bdi>]] as [string, React.ReactNode][]) : []),
    [t("startedOn"), joined],
  ];

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Block title={t("details")}>
        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
          {facts.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-muted">{label}</dt>
              <dd dir="auto">{value}</dd>
            </div>
          ))}
        </dl>
      </Block>
      <Block title={t("hoursThisMonth")}>
        {clock ? (
          <>
            <p className="text-3xl font-bold tabular-nums">{hm(clock.worked.total)}</p>
            <p className="text-sm text-muted">{t("plannedHours", { hours: hm(clock.planned_hours) })}</p>
            <Link href={`/team/time-clock/${member.user_id}?month=${month}`} className="w-fit text-sm text-primary-ink underline-offset-4 hover:underline">
              {t("openTimeClock")}
            </Link>
          </>
        ) : (
          <p className="text-sm text-muted">{t("noClockAccess")}</p>
        )}
      </Block>
      <Block title={t("upcomingShifts")}>
        {shifts.length === 0 ? (
          <p className="text-sm text-muted">{t("noShifts", { days: UPCOMING_DAYS })}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border text-sm">
            {shifts.map((shift) => (
              <li key={shift.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className="font-medium">{day(shift.starts_at)}</span>
                <span className="tabular-nums" dir="ltr">{span(shift.starts_at, shift.ends_at)}</span>
                <span className="text-muted" dir="auto">{[shift.location_name, shift.position].filter(Boolean).join(" · ")}</span>
              </li>
            ))}
          </ul>
        )}
        <Link href="/team/shifts" className="w-fit text-sm text-primary-ink underline-offset-4 hover:underline">
          {t("openShifts")}
        </Link>
      </Block>
      <Block title={t("classesTaught")}>
        {taught.length === 0 ? (
          <p className="text-sm text-muted">{t("noClasses", { days: UPCOMING_DAYS })}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border text-sm">
            {taught.map((session) => (
              <li key={session.id}>
                <Link href={`/schedule/${session.id}`} className="flex flex-wrap items-center justify-between gap-2 py-2 hover:text-primary-ink">
                  <span className="font-medium" dir="auto">{session.service.name}</span>
                  <span className="tabular-nums" dir="ltr">{`${day(session.starts_at)} ${span(session.starts_at, session.ends_at)}`}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Block>
    </div>
  );
}

/** Pay terms, Form 101 and pay components: the payroll file, kept right inside the card. */
export async function EmploymentTab({ member, context }: { member: Member; context: Context }) {
  const { api, scope, tenant } = context;
  const path = { ...scope, path: { user_id: member.user_id } };
  const [employment, forms, components] = await Promise.all([
    api.GET("/staff/{user_id}/employment", { params: path }).then(unwrap),
    api.GET("/staff/{user_id}/form101", { params: path }).then(unwrap),
    api.GET("/staff/{user_id}/pay-components", { params: path }).then(unwrap),
  ]);
  return (
    <PayrollFile
      userId={member.user_id}
      name={member.full_name ?? member.email}
      currency={tenant.currency}
      locale={tenant.locale}
      employment={employment}
      forms={forms}
      components={components}
      canManage={canManagePayroll(tenant)}
      thisYear={new Date().getFullYear()}
    />
  );
}

/** When the person can work shifts, their regular working hours and their time off. */
export async function AvailabilityTab({ member, context }: { member: Member; context: Context }) {
  const t = await getTranslations();
  const locale = await getLocale();
  const { api, scope, tenant } = context;
  const path = { ...scope, path: { user_id: member.user_id } };
  const canHours = tenant.permissions.includes("schedule.write");
  const [availability, hours, timeOff] = await Promise.all([
    api.GET("/staff/{user_id}/availability", { params: path }).then(unwrap),
    canHours ? api.GET("/staff/{user_id}/hours", { params: path }).then(unwrap) : Promise.resolve(null),
    canHours ? api.GET("/staff/{user_id}/time-off", { params: path }).then(unwrap) : Promise.resolve([]),
  ]);
  const weekStartsOn = weekStartFor(tenant.locale);
  const day = (value: string) => formatDay(value, locale, { weekday: "short", day: "numeric", month: "short" });

  return (
    <div className="flex flex-col gap-6">
      <section className="card flex flex-col gap-4 p-6">
        <h2 className="text-lg font-semibold">{t("availability.title")}</h2>
        <p className="text-sm text-muted">{t("availability.hint")}</p>
        <HoursForm
          save={saveAvailability.bind(null, member.user_id)}
          weekStartsOn={weekStartsOn}
          initial={toBlocks(availability.windows)}
          emptyLabel={t("availability.none")}
          savedLabel={t("availability.saved")}
        />
      </section>
      {hours && (
        <section className="card flex flex-col gap-4 p-6">
          <h2 className="text-lg font-semibold">{t("hours.title")}</h2>
          <p className="text-sm text-muted">{t("hours.subtitle", { name: isolate(member.full_name ?? member.email) })}</p>
          <HoursForm save={saveHours.bind(null, member.user_id)} weekStartsOn={weekStartsOn} initial={toBlocks(hours.blocks)} />
        </section>
      )}
      {canHours && (
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
                      {entry.starts_on === entry.ends_on ? day(entry.starts_on) : `${day(entry.starts_on)} - ${day(entry.ends_on)}`}
                    </span>
                    {entry.reason && <span dir="auto" className="text-muted"> · {entry.reason}</span>}
                  </span>
                  <form action={removeTimeOff.bind(null, member.user_id, entry.id)}>
                    <button type="submit" className="btn-link text-danger underline-offset-4 hover:underline">
                      {t("timeOff.remove")}
                    </button>
                  </form>
                </li>
              ))}
            </ul>
          )}
          <TimeOffForm userId={member.user_id} today={todayIn(tenant.time_zone)} />
        </section>
      )}
    </div>
  );
}

/** Form 101 per year and the employment notice. Payslips are issued from the pay run. */
export async function DocumentsTab({ member, context }: { member: Member; context: Context }) {
  const t = await getTranslations("payroll");
  const tc = await getTranslations("staffCard");
  const { api, scope } = context;
  const path = { ...scope, path: { user_id: member.user_id } };
  const [employment, forms] = await Promise.all([
    api.GET("/staff/{user_id}/employment", { params: path }).then(unwrap),
    api.GET("/staff/{user_id}/form101", { params: path }).then(unwrap),
  ]);
  const signed = forms.filter((form) => form.status === "submitted");
  return (
    <Block title={t("documents.title")}>
      <ul className="flex flex-col divide-y divide-border text-sm">
        {signed.map((form) => (
          <li key={form.tax_year} className="flex items-center justify-between gap-3 py-2.5">
            <span>{t("form101.year", { year: form.tax_year })}</span>
            <a className="text-primary-ink underline-offset-4 hover:underline" href={`/team/${member.user_id}/payroll/form101/${form.tax_year}/pdf`} download>
              {t("form101.pdf")}
            </a>
          </li>
        ))}
        <li className="flex items-center justify-between gap-3 py-2.5">
          <span>{t("documents.notice")}</span>
          <span className="text-muted">{employment.employment_notice_date ?? t("documents.notSent")}</span>
        </li>
      </ul>
      {signed.length === 0 && <p className="text-sm text-muted">{t("documents.none")}</p>}
      <Link href="/team/payroll" className="w-fit text-sm text-primary-ink underline-offset-4 hover:underline">
        {tc("openPayRun")}
      </Link>
    </Block>
  );
}

/** Whether the person may use the AI team and how many credits they used this month. Their own
 * quota and pace arrive with the AI usage rules; until then everyone shares the business budget. */
export async function AiTab({ member, context }: { member: Member; context: Context }) {
  const t = await getTranslations("staffCard");
  const locale = await getLocale();
  const { api, scope } = context;
  const usage = await api.GET("/ai/usage", { params: scope }).then((r) => r.data ?? null);
  const allowed = member.permissions.includes("ai.use");
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  const mine = usage?.by_user.find((row) => row.key === member.user_id)?.credits ?? 0;
  return (
    <Block title={t("aiTitle")}>
      <p className="flex items-center gap-2 text-sm">
        <span aria-hidden="true" className={`size-2 rounded-full ${allowed ? "bg-success" : "bg-muted"}`} />
        {allowed ? t("aiAllowed") : t("aiNotAllowed")}
      </p>
      {usage && (
        <>
          <p className="text-3xl font-bold tabular-nums">{number.format(mine)}</p>
          <p className="text-sm text-muted">
            {t("aiUsedThisMonth", { used: number.format(usage.credits_used), included: number.format(usage.credits_included) })}
          </p>
        </>
      )}
      <p className="text-sm text-muted">{t("aiHint")}</p>
      <Link href="/ai" className="w-fit text-sm text-primary-ink underline-offset-4 hover:underline">
        {t("openAi")}
      </Link>
    </Block>
  );
}

/** The role and what it allows, so a manager can check a person before or after changing it. */
export async function PermissionsTab({ member, context }: { member: Member; context: Context }) {
  const t = await getTranslations("staffCard");
  const tAll = await getTranslations();
  const roles = await context.api.GET("/roles", { params: context.scope }).then(unwrap);
  return (
    <Block title={t("permissionsTitle")}>
      <p className="text-sm">
        {t("roleIs", { role: member.custom_role_name ?? tAll(`roles.${member.role}` as "roles.staff") })}
      </p>
      <PermissionList all={roles.permissions} allowed={member.permissions} />
      <p className="text-xs text-muted">{tAll("team.permissionsHint")}</p>
      <div className="flex flex-wrap gap-4 text-sm">
        <Link href="/team" className="text-primary-ink underline-offset-4 hover:underline">{t("changeRole")}</Link>
        <Link href="/team/roles" className="text-primary-ink underline-offset-4 hover:underline">{tAll("team.manageRoles")}</Link>
      </div>
    </Block>
  );
}
