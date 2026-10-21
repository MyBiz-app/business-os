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

import { CollapsibleSection } from "@/components/ui/collapsible-section";

import { AiMemberForm } from "./ai-member-form";
import { PayrollFile } from "./payroll/payroll-file";
import { saveAvailability } from "./availability/actions";
import { removeTimeOff, saveHours } from "./hours/actions";
import { TimeOffForm } from "./hours/time-off";
import { Button } from "@/components/ui/button";

type Context = Awaited<ReturnType<typeof getTenant>>;
type Member = { user_id: string; email: string; full_name: string | null; role: string; custom_role_id: string | null; custom_role_name: string | null; location_ids: string[]; home_location_id: string | null; joined_at: string; job_title: string | null; phone: string | null; permissions: string[] };

const UPCOMING_DAYS = 14;

/** A section of the card that folds; only the first one of a tab starts open. The choice is
 * remembered per browser and per person, so folding one card never folds another. */
function Block({ title, id, memberId, first = false, children }: { title: string; id: string; memberId: string; first?: boolean; children: React.ReactNode }) {
  return (
    <CollapsibleSection title={title} defaultOpen={first} storageKey={`staff-card-${memberId}-${id}`}>
      <div className="flex flex-col gap-3">{children}</div>
    </CollapsibleSection>
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
    <div className="flex flex-col gap-4">
      <Block memberId={member.user_id} id="details" first title={t("details")}>
        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
          {facts.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-muted">{label}</dt>
              <dd dir="auto">{value}</dd>
            </div>
          ))}
        </dl>
      </Block>
      <Block memberId={member.user_id} id="hours" title={t("hoursThisMonth")}>
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
      <Block memberId={member.user_id} id="shifts" title={t("upcomingShifts")}>
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
      <Block memberId={member.user_id} id="classes" title={t("classesTaught")}>
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
      <CollapsibleSection title={t("availability.title")} description={t("availability.hint")} defaultOpen storageKey="staff-card-availability">
        <HoursForm
          save={saveAvailability.bind(null, member.user_id)}
          weekStartsOn={weekStartsOn}
          initial={toBlocks(availability.windows)}
          emptyLabel={t("availability.none")}
          savedLabel={t("availability.saved")}
        />
      </CollapsibleSection>
      {hours && (
        <CollapsibleSection title={t("hours.title")} description={t("hours.subtitle", { name: isolate(member.full_name ?? member.email) })} defaultOpen storageKey="staff-card-hours">
          <HoursForm save={saveHours.bind(null, member.user_id)} weekStartsOn={weekStartsOn} initial={toBlocks(hours.blocks)} />
        </CollapsibleSection>
      )}
      {canHours && (
        <CollapsibleSection title={t("timeOff.title")} description={t("timeOff.hint")} defaultOpen storageKey="staff-card-time-off">
          <div className="flex flex-col gap-4">
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
                    <Button variant="plain" type="submit" className="btn-link text-danger underline-offset-4 hover:underline">
                      {t("timeOff.remove")}
                    </Button>
                  </form>
                </li>
              ))}
            </ul>
          )}
          <TimeOffForm userId={member.user_id} today={todayIn(tenant.time_zone)} />
          </div>
        </CollapsibleSection>
      )}
    </div>
  );
}

/** Form 101 per year, the employment notice, the payslips and the contract. Payslips are issued from
 * the pay run and filed in the business's files; a person only sees here the folders they may open. */
export async function DocumentsTab({ member, context }: { member: Member; context: Context }) {
  const t = await getTranslations("payroll");
  const tc = await getTranslations("staffCard");
  const locale = await getLocale();
  const { api, scope, tenant } = context;
  const path = { ...scope, path: { user_id: member.user_id } };
  const [employment, forms, folders] = await Promise.all([
    api.GET("/staff/{user_id}/employment", { params: path }).then(unwrap),
    api.GET("/staff/{user_id}/form101", { params: path }).then(unwrap),
    api.GET("/files/folders", { params: scope }).then((r) => r.data ?? []),
  ]);
  const signed = forms.filter((form) => form.status === "submitted");
  const filed = async (systemKey: string) => {
    const folder = folders.find((f) => f.system_key === systemKey);
    if (!folder) return null;
    const files = await api.GET("/files", { params: { ...scope, query: { folder_id: folder.id, archived: false } } }).then((r) => r.data ?? []);
    return files.filter((file) => file.owner_user_id === member.user_id);
  };
  const [payslips, contract] = await Promise.all([filed("payroll"), filed("employees")]);
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: tenant.time_zone });
  const fileList = (files: NonNullable<typeof payslips>, empty: string) =>
    files.length === 0 ? (
      <p className="text-sm text-muted">{empty}</p>
    ) : (
      <ul className="flex flex-col divide-y divide-border text-sm">
        {files.map((file) => (
          <li key={file.id} className="flex items-center justify-between gap-3 py-2.5">
            <span className="min-w-0">
              <span className="block truncate" dir="auto">{file.name}</span>
              <span className="text-xs text-muted">{date.format(new Date(file.created_at))}</span>
            </span>
            <a className="shrink-0 text-primary-ink underline-offset-4 hover:underline" href={`/files/${file.id}/file`} download>
              {tc("download")}
            </a>
          </li>
        ))}
      </ul>
    );
  return (
    <div className="flex flex-col gap-6">
      <Block memberId={member.user_id} id="documents" first title={t("documents.title")}>
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
      {payslips && (
        <Block memberId={member.user_id} id="payslips" title={tc("payslipsTitle")}>
          {fileList(payslips, tc("noPayslips"))}
        </Block>
      )}
      {contract && (
        <Block memberId={member.user_id} id="contract" title={tc("contractTitle")}>
          {fileList(contract, tc("noContract"))}
          <Link href={`/files?folder=${folders.find((f) => f.system_key === "employees")?.id}`} className="w-fit text-sm text-primary-ink underline-offset-4 hover:underline">
            {tc("openFiles")}
          </Link>
        </Block>
      )}
    </div>
  );
}

/** Whether the person may use the AI team, their own monthly limit and daily pace, and what they used. */
export async function AiTab({ member, context }: { member: Member; context: Context }) {
  const t = await getTranslations("staffCard");
  const locale = await getLocale();
  const { api, scope } = context;
  const [ai, team] = await Promise.all([
    api.GET("/ai/members/{user_id}", { params: { ...scope, path: { user_id: member.user_id } } }).then((r) => r.data ?? null),
    api.GET("/ai/team", { params: scope }).then((r) => r.data ?? null),
  ]);
  // Open to this person by their role; "locked" ones need a module the business does not have.
  const agents = (team?.agents ?? []).filter((agent) => agent.state !== "disabled" && (agent.allowed_roles ?? []).includes(member.role));
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  return (
    <div className="flex flex-col gap-6">
    <Block memberId={member.user_id} id="ai" first title={t("aiTitle")}>
      {ai ? (
        <>
          <dl className="grid grid-cols-2 gap-4 sm:max-w-md">
            <div>
              <dt className="text-sm text-muted">{t("ai.usedMonth")}</dt>
              <dd className="text-3xl font-bold tabular-nums">{number.format(ai.used_month)}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted">{t("ai.usedToday", { limit: ai.day_limit === null ? "∞" : number.format(ai.day_limit) })}</dt>
              <dd className="text-3xl font-bold tabular-nums">{number.format(ai.used_today)}</dd>
            </div>
          </dl>
          <AiMemberForm ai={ai} />
        </>
      ) : (
        <p className="text-sm text-muted">{t("aiNotAllowed")}</p>
      )}
      <p className="text-sm text-muted">{t("aiHint")}</p>
      <Link href="/ai" className="w-fit text-sm text-primary-ink underline-offset-4 hover:underline">
        {t("openAi")}
      </Link>
    </Block>
    <Block memberId={member.user_id} id="agents" title={t("agentsTitle")}>
      <p className="text-sm text-muted">{t("agentsHint")}</p>
      {agents.length === 0 ? (
        <p className="text-sm">{t("noAgents")}</p>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2 min-[120rem]:grid-cols-3">
          {agents.map((agent) => (
            <li key={agent.key} className="flex items-center gap-3 rounded-xl border border-border px-3 py-2.5 text-sm">
              <span aria-hidden="true" className="size-3 shrink-0 rounded-full" style={{ background: agent.color }} />
              <span className="min-w-0">
                <span className="block truncate font-medium" dir="auto">{agent.name}</span>
                <span className="block truncate text-xs text-muted" dir="auto">
                  {agent.state === "locked" ? t("agentLocked") : agent.role_title}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
      <Link href="/ai" className="w-fit text-sm text-primary-ink underline-offset-4 hover:underline">
        {t("openAgents")}
      </Link>
    </Block>
    </div>
  );
}

/** The role and what it allows, so a manager can check a person before or after changing it. */
export async function PermissionsTab({ member, context }: { member: Member; context: Context }) {
  const t = await getTranslations("staffCard");
  const tAll = await getTranslations();
  const roles = await context.api.GET("/roles", { params: context.scope }).then(unwrap);
  return (
    <Block memberId={member.user_id} id="permissions" first title={t("permissionsTitle")}>
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
