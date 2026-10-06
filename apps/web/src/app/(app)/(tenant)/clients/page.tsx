import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { termsOf } from "@business-os/verticals";

import { Avatar } from "@/components/avatar";
import { unwrap } from "@/lib/api";
import { formatDay, todayIn } from "@/lib/dates";
import { canWriteClients } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { StatusBadge } from "./status-badge";
import { ScrollRegion } from "@/components/scroll-region";

const PAGE_SIZE = 25;
const STATUSES = ["active", "lead", "inactive"] as const;
type Status = (typeof STATUSES)[number];
const PLANS = ["valid", "none"] as const;
type PlanFilter = (typeof PLANS)[number];
const ABSENCES = [14, 30, 60] as const;

export default async function ClientsPage({ searchParams }: PageProps<"/clients">) {
  const t = await getTranslations();
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("clients.read");
  const params = await searchParams;

  const search = typeof params.q === "string" ? params.q : "";
  const status = STATUSES.find((s) => s === params.status) as Status | undefined;
  const plan = PLANS.find((p) => p === params.plan) as PlanFilter | undefined;
  const absent = ABSENCES.find((d) => String(d) === params.absent);
  const page = Math.max(1, Number(params.page) || 1);

  const result = unwrap(
    await api.GET("/clients", {
      params: {
        ...scope,
        query: {
          search: search || undefined,
          status,
          plan,
          absent_days: absent,
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
  const pageHref = (target: number) => {
    const query = new URLSearchParams();
    if (search) query.set("q", search);
    if (status) query.set("status", status);
    if (plan) query.set("plan", plan);
    if (absent) query.set("absent", String(absent));
    query.set("page", String(target));
    return `/clients?${query}`;
  };

  return (
    <main className="enter mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 id="clients-heading" className="text-3xl font-bold">{term("clients")}</h1>
          <p className="text-sm text-muted">{t("clients.total", { count: result.total })}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {tenant.modules.includes("client_app") && (
            <Link href="/clients/join" className="btn-secondary px-4 py-2.5">
              {t("join.inviteToApp")}
            </Link>
          )}
          {canWriteClients(tenant) && (
            <Link href="/clients/import" className="btn-secondary px-4 py-2.5">
              {t("clientImport.button")}
            </Link>
          )}
          {canWriteClients(tenant) && (
            <Link
              href="/clients/new"
              className="btn-primary px-4 py-2.5"
            >
              {term("addClient")}
            </Link>
          )}
        </div>
      </div>

      <form role="search" className="flex flex-wrap items-end gap-3">
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
        <button type="submit" className="btn-secondary px-4 py-2">
          {t("clients.search")}
        </button>
      </form>

      {result.items.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border p-10 text-center text-muted">
          {search || status || plan || absent ? term("noResults") : term("noClients")}
        </p>
      ) : (
        <ScrollRegion labelledBy="clients-heading" className="rounded-2xl border border-border">
          <table className="w-full text-start text-sm">
            <thead className="bg-surface text-muted">
              <tr>
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("clients.name")}</th>
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("clients.phone")}</th>
                <th scope="col" className="hidden px-4 py-3 text-start font-medium xl:table-cell">{t("clients.email")}</th>
                <th scope="col" className="hidden px-4 py-3 text-start font-medium lg:table-cell">{t("clients.list.plan")}</th>
                <th scope="col" className="hidden px-4 py-3 text-start font-medium sm:table-cell">{t("clients.list.lastVisit")}</th>
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("clients.status")}</th>
              </tr>
            </thead>
            <tbody>
              {result.items.map((client) => (
                <tr key={client.id} className="border-t border-border transition-colors hover:bg-primary/4">
                  <td className="px-4 py-2.5">
                    <Link href={`/clients/${client.id}`} className="group flex items-center gap-3 font-medium">
                      <Avatar id={client.id} name={[client.first_name, client.last_name].filter(Boolean).join(" ")} />
                      <span className="text-primary underline-offset-4 group-hover:underline">
                        {[client.first_name, client.last_name].filter(Boolean).join(" ")}
                      </span>
                    </Link>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3" dir="ltr">{client.phone}</td>
                  <td className="hidden max-w-56 truncate px-4 py-3 xl:table-cell" dir="ltr">{client.email}</td>
                  <td className="hidden px-4 py-3 lg:table-cell">
                    {client.plan_name ? (
                      <span className="flex flex-col">
                        <span className="font-medium">{client.plan_name}</span>
                        {client.plan_ends_on && (
                          <span className="text-xs text-muted">{t("clients.list.planUntil", { date: shortDate(client.plan_ends_on) })}</span>
                        )}
                      </span>
                    ) : (
                      <span className="text-muted">{t("clients.list.noPlan")}</span>
                    )}
                  </td>
                  <td className="hidden whitespace-nowrap px-4 py-3 sm:table-cell">
                    {client.last_visit ? sinceVisit(client.last_visit) : <span className="text-muted">{t("clients.list.never")}</span>}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={client.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      )}

      {pages > 1 && (
        <nav aria-label={t("clients.total", { count: result.total })} className="flex items-center justify-between text-sm">
          {page > 1 ? <Link href={pageHref(page - 1)} className="text-primary">{t("clients.previous")}</Link> : <span />}
          <span className="text-muted">{t("clients.pageOf", { page, pages })}</span>
          {page < pages ? <Link href={pageHref(page + 1)} className="text-primary">{t("clients.next")}</Link> : <span />}
        </nav>
      )}
    </main>
  );
}
