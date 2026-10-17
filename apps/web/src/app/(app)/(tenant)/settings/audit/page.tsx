import type { Metadata } from "next";
import { getLocale, getMessages, getTranslations } from "next-intl/server";
import Link from "next/link";
import { redirect } from "next/navigation";
import { BRAND } from "@business-os/i18n/brand";

import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { ScrollRegion } from "@/components/scroll-region";
import { unwrap } from "@/lib/api";
import { getTenant } from "@/lib/tenant";

const CATEGORIES = ["team", "settings", "security", "payroll", "privacy", "export", "support", "other"] as const;
type Category = (typeof CATEGORIES)[number];

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("auditLog");
  return { title: `${t("title")} · ${BRAND.name}` };
}

const one = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value) ?? "";

/** Who did what in the business: roles, team, settings, exports, sign-ins. Owners and managers. */
export default async function AuditLogPage({ searchParams }: PageProps<"/settings/audit">) {
  const t = await getTranslations("auditLog");
  const locale = await getLocale();
  const { api, scope, tenant } = await getTenant();
  // The API refuses people kept to some branches; the screen follows.
  if (tenant.role !== "owner" && tenant.role !== "manager") redirect("/dashboard");
  const query = await searchParams;
  const category = CATEGORIES.find((c) => c === one(query.category)) as Category | undefined;
  const actorId = one(query.actor);
  const from = /^\d{4}-\d{2}-\d{2}$/.test(one(query.from)) ? one(query.from) : undefined;
  const to = /^\d{4}-\d{2}-\d{2}$/.test(one(query.to)) ? one(query.to) : undefined;
  const cursor = one(query.cursor) || undefined;
  const filters = { actor_id: actorId || undefined, category, date_from: from, date_to: to };

  const [log, team] = await Promise.all([
    api.GET("/audit-log", { params: { ...scope, query: { ...filters, cursor } } }),
    api.GET("/staff", { params: scope }).then(unwrap),
  ]);
  if (log.response.status === 403) redirect("/dashboard");
  const page = unwrap(log);
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone: tenant.time_zone });
  const actions: Record<string, string> = (await getMessages()).auditLog.actions;
  const label = (action: string) => actions[action.replace(".", "_")] ?? action;
  const detail = (details: Record<string, unknown>) =>
    Object.entries(details)
      .filter(([, value]) => value !== null && value !== "" && !(Array.isArray(value) && value.length === 0))
      .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : String(value)}`)
      .join(" · ");
  const params = new URLSearchParams(
    Object.entries({ actor: actorId, category, from, to }).filter(([, v]) => v) as [string, string][],
  );
  const exportHref = `/settings/audit/export${params.size ? `?${params}` : ""}`;
  const olderHref = page.next_cursor ? `/settings/audit?${new URLSearchParams([...params, ["cursor", page.next_cursor]])}` : null;

  return (
    <Container as="main" size="wide" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <Link href="/settings" className="text-sm text-primary-ink underline-offset-4 hover:underline">
        {t("back")}
      </Link>
      <PageHeader titleId="audit-heading" title={t("title")} description={t("subtitle")} />
      <form method="get" className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("person")}
          <select name="actor" defaultValue={actorId} className="control px-3 py-2 font-normal">
            <option value="">{t("everyone")}</option>
            {team.members.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.full_name || m.email}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("kind")}
          <select name="category" defaultValue={category ?? ""} className="control px-3 py-2 font-normal">
            <option value="">{t("allKinds")}</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {t(`categories.${c}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("from")}
          <input type="date" name="from" defaultValue={from} className="control px-3 py-2 font-normal" />
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("to")}
          <input type="date" name="to" defaultValue={to} className="control px-3 py-2 font-normal" />
        </label>
        <button type="submit" className="btn-primary px-4 py-2.5 text-sm">
          {t("filter")}
        </button>
        <a href={exportHref} className="btn-secondary px-4 py-2.5 text-sm">
          {t("exportCsv")}
        </a>
      </form>
      {page.entries.length === 0 ? (
        <EmptyState variant="list">{t("empty")}</EmptyState>
      ) : (
        <ScrollRegion labelledBy="audit-heading" className="rounded-2xl border border-border">
          <table className="w-full text-sm">
            <thead className="bg-surface text-muted">
              <tr>
                {(["when", "who", "kind", "action", "details"] as const).map((key) => (
                  <th key={key} scope="col" className="px-4 py-3 text-start font-medium">
                    {t(key)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {page.entries.map((entry) => (
                <tr key={entry.id} className="border-t border-border align-top">
                  <td className="whitespace-nowrap px-4 py-2.5">{when.format(new Date(entry.occurred_at))}</td>
                  <td className="px-4 py-2.5" dir="auto">
                    {entry.actor_name || entry.actor_email || t("system")}
                    {entry.actor_type === "platform" && <span className="ms-2 text-xs text-muted">{t("mybizTeam")}</span>}
                  </td>
                  <td className="px-4 py-2.5">{t(`categories.${entry.category as Category}`)}</td>
                  <td className="px-4 py-2.5 font-medium">{label(entry.action)}</td>
                  <td className="px-4 py-2.5 text-muted" dir="auto">{detail(entry.details)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      )}
      <nav aria-label={t("title")} className="flex items-center justify-between text-sm">
        {cursor ? <Link scroll={false} href={`/settings/audit${params.size ? `?${params}` : ""}`} className="text-primary-ink">{t("newest")}</Link> : <span />}
        {olderHref ? <Link scroll={false} href={olderHref} className="text-primary-ink">{t("older")}</Link> : <span />}
      </nav>
      <p className="text-xs text-muted">{t("retention")}</p>
    </Container>
  );
}
