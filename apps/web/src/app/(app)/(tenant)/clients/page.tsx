import { X } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { termsOf } from "@business-os/verticals";

import { Avatar } from "@/components/avatar";
import { unwrap } from "@/lib/api";
import { formatDay, isDay, todayIn } from "@/lib/dates";
import { canWriteClients } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { Badge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { CardTransition } from "@/components/ui/page-transition";

import { addMeAsClient } from "./actions";
import { StatusBadge } from "./status-badge";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/empty-state";
import { openedId, withOpen } from "@/lib/open-window";

import { ClientWindow } from "./client-window";

const PAGE_SIZE = 25;
const STATUSES = ["active", "lead", "inactive"] as const;
type Status = (typeof STATUSES)[number];
const PLANS = ["valid", "none"] as const;
type PlanFilter = (typeof PLANS)[number];
const ABSENCES = [14, 30, 60] as const;
const STAFF = ["only", "exclude"] as const;

export default async function ClientsPage({ searchParams }: PageProps<"/clients">) {
  const t = await getTranslations();
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("clients.read");
  const params = await searchParams;

  const search = typeof params.q === "string" ? params.q : "";
  const status = STATUSES.find((s) => s === params.status) as Status | undefined;
  const plan = PLANS.find((p) => p === params.plan) as PlanFilter | undefined;
  const absent = ABSENCES.find((d) => String(d) === params.absent);
  const staff = STAFF.find((v) => v === params.staff);
  const page = Math.max(1, Number(params.page) || 1);
  // Date filters that come from the dashboard tiles ("new clients", "no-shows").
  const day = (value: unknown) => (isDay(value) ? value : undefined);
  const joined = { from: day(params.joined_from), to: day(params.joined_to) };
  const noShow = { from: day(params.no_show_from), to: day(params.no_show_to) };

  const result = unwrap(
    await api.GET("/clients", {
      params: {
        ...scope,
        query: {
          search: search || undefined,
          status,
          plan,
          absent_days: absent,
          staff,
          joined_from: joined.from,
          joined_to: joined.to,
          no_show_from: noShow.from,
          no_show_to: noShow.to,
          limit: PAGE_SIZE,
          offset: (page - 1) * PAGE_SIZE,
        },
      },
    }),
  );
  const term = (key: string) => t(`terms.${termsOf(tenant.vertical)}.${key}` as "terms.fitness.clients");
  const today = todayIn(tenant.time_zone);
  const shortDate = (day: string) => formatDay(day, locale, { day: "numeric", month: "short" });
  const sinceVisit = (day: string) => {
    const days = Math.round((Date.parse(today) - Date.parse(day)) / 86_400_000);
    return days <= 0 ? t("clients.list.today") : days < 30 ? t("clients.list.daysAgo", { days }) : shortDate(day);
  };
  const pages = Math.max(1, Math.ceil(result.total / PAGE_SIZE));
  const dateFilters = { joined_from: joined.from, joined_to: joined.to, no_show_from: noShow.from, no_show_to: noShow.to };
  const rangeText = (range: { from?: string; to?: string }) =>
    [range.from, range.to].map((value) => (value ? formatDay(value, locale, { day: "numeric", month: "short" }) : "...")).join(" - ");
  // What the list is narrowed to by date, each with a link that removes just that filter.
  const dateChips = [
    joined.from || joined.to ? { key: "joined", text: t("clients.joinedChip", { range: rangeText(joined) }), keys: ["joined_from", "joined_to"] } : null,
    noShow.from || noShow.to ? { key: "noShow", text: t("clients.noShowChip", { range: rangeText(noShow) }), keys: ["no_show_from", "no_show_to"] } : null,
  ].filter((chip) => chip !== null);
  const withoutKeys = (keys: string[]) => {
    const query = new URLSearchParams();
    if (search) query.set("q", search);
    if (status) query.set("status", status);
    if (plan) query.set("plan", plan);
    if (staff) query.set("staff", staff);
    if (absent) query.set("absent", String(absent));
    for (const [key, value] of Object.entries(dateFilters)) if (value && !keys.includes(key)) query.set(key, value);
    return query.size ? `/clients?${query}` : "/clients";
  };
  const pageHref = (target: number) => {
    const query = new URLSearchParams();
    if (search) query.set("q", search);
    if (status) query.set("status", status);
    if (plan) query.set("plan", plan);
    if (staff) query.set("staff", staff);
    if (absent) query.set("absent", String(absent));
    for (const [key, value] of Object.entries(dateFilters)) if (value) query.set(key, value);
    query.set("page", String(target));
    return `/clients?${query}`;
  };

  const opened = openedId(params);
  const filtered = Boolean(search || status || plan || absent || staff || dateChips.length > 0);
  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader
        titleId="clients-heading"
        title={term("clients")}
        description={t("clients.total", { count: result.total })}
        actions={
          <>
            {tenant.modules.includes("client_app") && (
              <ButtonLink href="/clients/join" variant="secondary">
                {t("join.inviteToApp")}
              </ButtonLink>
            )}
            {canWriteClients(tenant) && (
              <form action={addMeAsClient}>
                <Button type="submit" variant="secondary">
                  {t("clients.addMe")}
                </Button>
              </form>
            )}
            {canWriteClients(tenant) && (
              <ButtonLink href="/clients/import" variant="secondary">
                {t("clientImport.button")}
              </ButtonLink>
            )}
            {canWriteClients(tenant) && (
              <ButtonLink href="/clients/new" variant="primary">
                {term("addClient")}
              </ButtonLink>
            )}
          </>
        }
      />

      <form role="search" className="flex flex-wrap items-end gap-3">
        {Object.entries(dateFilters).map(([key, value]) => (value ? <input key={key} type="hidden" name={key} value={value} /> : null))}
        <label className="flex min-w-60 flex-1 flex-col gap-1.5 text-sm font-medium">
          {t("clients.search")}
          <input
            type="search"
            name="q"
            defaultValue={search}
            placeholder={term("searchClients")}
            className="control px-3 py-2 font-normal"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("clients.status")}
          <select
            name="status"
            defaultValue={status ?? ""}
            className="control px-3 py-2 font-normal"
          >
            <option value="">{t("clients.allStatuses")}</option>
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {t(`clients.statuses.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("clients.planFilter")}
          <select name="plan" defaultValue={plan ?? ""} className="control px-3 py-2 font-normal">
            <option value="">{t("clients.planAny")}</option>
            {PLANS.map((value) => (
              <option key={value} value={value}>
                {t(`clients.plans.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("clients.absentFilter")}
          <select name="absent" defaultValue={absent ?? ""} className="control px-3 py-2 font-normal">
            <option value="">{t("clients.absentAny")}</option>
            {ABSENCES.map((days) => (
              <option key={days} value={days}>
                {t("clients.absentDays", { days })}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("clients.staffFilter")}
          <select name="staff" defaultValue={staff ?? ""} className="control px-3 py-2 font-normal">
            <option value="">{t("clients.staffAny")}</option>
            {STAFF.map((value) => (
              <option key={value} value={value}>
                {t(`clients.staffOptions.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <Button type="submit" variant="secondary">
          {t("clients.search")}
        </Button>
      </form>

      {dateChips.length > 0 && (
        <ul className="flex flex-wrap items-center gap-2" aria-label={t("clients.activeFilters")}>
          {dateChips.map((chip) => (
            <li key={chip.key}>
              <Link
                href={withoutKeys(chip.keys)}
                scroll={false}
                className="inline-flex items-center gap-1.5 rounded-full bg-primary-subtle px-3 py-1 text-sm font-medium text-primary-ink transition-colors hover:bg-primary/20"
              >
                {chip.text}
                <X aria-hidden="true" className="size-3.5" />
                <span className="sr-only">{t("clients.removeFilter")}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {result.items.length === 0 ? (
        <EmptyState
          variant="people"
          action={
            filtered ? (
              <ButtonLink href="/clients" variant="secondary">
                {t("clients.clearFilters")}
              </ButtonLink>
            ) : (
              canWriteClients(tenant) && (
                <ButtonLink href="/clients/new" variant="primary">
                  {term("addClient")}
                </ButtonLink>
              )
            )
          }
        >
          {filtered ? term("noResults") : term("noClients")}
        </EmptyState>
      ) : (
        <DataTable
          labelledBy="clients-heading"
          rows={result.items}
          rowKey={(client) => client.id}
          columns={[
            {
              key: "name",
              header: t("clients.name"),
              cell: (client) => (
                <CardTransition name={`client-${client.id}`}>
                  <Link scroll={false} href={withOpen("/clients", params, client.id)} className="group flex items-center gap-3 font-medium">
                    <Avatar id={client.id} name={[client.first_name, client.last_name].filter(Boolean).join(" ")} />
                    <span dir="auto" className="text-primary-ink underline-offset-4 group-hover:underline">
                      {[client.first_name, client.last_name].filter(Boolean).join(" ")}
                    </span>
                    {client.is_staff && <Badge tone="primary">{t("clients.staffBadge")}</Badge>}
                  </Link>
                </CardTransition>
              ),
            },
            { key: "phone", header: t("clients.phone"), nowrap: true, cell: (client) => <bdi dir="ltr">{client.phone}</bdi> },
            {
              key: "email",
              header: t("clients.email"),
              hideBelow: "xl",
              className: "max-w-56 truncate",
              cell: (client) => <bdi dir="ltr">{client.email}</bdi>,
            },
            {
              key: "plan",
              header: t("clients.list.plan"),
              hideBelow: "lg",
              cell: (client) =>
                client.plan_name ? (
                  <span className="flex flex-col">
                    <span dir="auto" className="font-medium">{client.plan_name}</span>
                    {client.plan_ends_on && (
                      <span className="text-xs text-muted">{t("clients.list.planUntil", { date: shortDate(client.plan_ends_on) })}</span>
                    )}
                  </span>
                ) : (
                  <span className="text-muted">{t("clients.list.noPlan")}</span>
                ),
            },
            {
              key: "lastVisit",
              header: t("clients.list.lastVisit"),
              hideBelow: "sm",
              nowrap: true,
              cell: (client) => (client.last_visit ? sinceVisit(client.last_visit) : <span className="text-muted">{t("clients.list.never")}</span>),
            },
            { key: "status", header: t("clients.status"), cell: (client) => <StatusBadge status={client.status} /> },
          ]}
        />
      )}

      {pages > 1 && (
        <nav aria-label={t("clients.total", { count: result.total })} className="flex items-center justify-between text-sm">
          {page > 1 ? <ButtonLink scroll={false} href={pageHref(page - 1)} variant="quiet">{t("clients.previous")}</ButtonLink> : <span />}
          <span className="text-muted">{t("clients.pageOf", { page, pages })}</span>
          {page < pages ? <ButtonLink scroll={false} href={pageHref(page + 1)} variant="quiet">{t("clients.next")}</ButtonLink> : <span />}
        </nav>
      )}
      {opened && <ClientWindow id={opened} closeHref={withOpen("/clients", params, null)} />}
    </Container>
  );
}
