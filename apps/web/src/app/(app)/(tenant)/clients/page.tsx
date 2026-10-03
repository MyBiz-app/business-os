import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { unwrap } from "@/lib/api";
import { canWriteClients } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { StatusBadge } from "./status-badge";

const PAGE_SIZE = 25;
const STATUSES = ["active", "lead", "inactive"] as const;
type Status = (typeof STATUSES)[number];

export default async function ClientsPage({ searchParams }: PageProps<"/clients">) {
  const t = await getTranslations();
  const { tenant, api, scope } = await getTenant();
  const params = await searchParams;

  const search = typeof params.q === "string" ? params.q : "";
  const status = STATUSES.find((s) => s === params.status) as Status | undefined;
  const page = Math.max(1, Number(params.page) || 1);

  const result = unwrap(
    await api.GET("/clients", {
      params: {
        ...scope,
        query: { search: search || undefined, status, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE },
      },
    }),
  );
  const term = (key: string) => t(`terms.${tenant.vertical}.${key}` as "terms.fitness.clients");
  const pages = Math.max(1, Math.ceil(result.total / PAGE_SIZE));
  const pageHref = (target: number) => {
    const query = new URLSearchParams();
    if (search) query.set("q", search);
    if (status) query.set("status", status);
    query.set("page", String(target));
    return `/clients?${query}`;
  };

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold">{term("clients")}</h1>
          <p className="text-sm text-muted">{t("clients.total", { count: result.total })}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {tenant.modules.includes("client_app") && (
            <Link href="/clients/join" className="rounded-lg border border-border px-4 py-2.5 font-semibold">
              {t("join.inviteToApp")}
            </Link>
          )}
          {canWriteClients(tenant) && (
            <Link
              href="/clients/new"
              className="rounded-lg bg-primary px-4 py-2.5 font-semibold text-on-primary"
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
            className="rounded-lg border border-border bg-background px-3 py-2 font-normal"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("clients.status")}
          <select
            name="status"
            defaultValue={status ?? ""}
            className="rounded-lg border border-border bg-background px-3 py-2 font-normal"
          >
            <option value="">{t("clients.allStatuses")}</option>
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {t(`clients.statuses.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="rounded-lg border border-border px-4 py-2 font-medium">
          {t("clients.search")}
        </button>
      </form>

      {result.items.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border p-10 text-center text-muted">
          {search || status ? term("noResults") : term("noClients")}
        </p>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-border">
          <table className="w-full text-start text-sm">
            <thead className="bg-surface text-muted">
              <tr>
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("clients.name")}</th>
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("clients.phone")}</th>
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("clients.email")}</th>
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("clients.status")}</th>
              </tr>
            </thead>
            <tbody>
              {result.items.map((client) => (
                <tr key={client.id} className="border-t border-border">
                  <td className="px-4 py-3">
                    <Link href={`/clients/${client.id}`} className="font-medium text-primary underline-offset-4 hover:underline">
                      {[client.first_name, client.last_name].filter(Boolean).join(" ")}
                    </Link>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3" dir="ltr">{client.phone}</td>
                  <td className="whitespace-nowrap px-4 py-3" dir="ltr">{client.email}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={client.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pages > 1 && (
        <nav aria-label={t("clients.total", { count: result.total })} className="flex items-center justify-between text-sm">
          {page > 1 ? <Link href={pageHref(page - 1)} className="text-primary">{t("clients.previous")}</Link> : <span />}
          <span className="text-muted">{page} / {pages}</span>
          {page < pages ? <Link href={pageHref(page + 1)} className="text-primary">{t("clients.next")}</Link> : <span />}
        </nav>
      )}
    </main>
  );
}
