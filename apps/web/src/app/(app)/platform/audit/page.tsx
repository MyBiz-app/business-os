import type { Metadata } from "next";
import { getLocale, getMessages, getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BRAND } from "@business-os/i18n/brand";

import { ScrollRegion } from "@/components/scroll-region";
import { unwrap } from "@/lib/api";
import { getPlatform } from "@/lib/platform";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/empty-state";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("platform.audit");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** What the MyBiz team did (owners only). */
const PAGE_SIZE = 50;

export default async function PlatformAuditPage({ searchParams }: PageProps<"/platform/audit">) {
  const t = await getTranslations("platform");
  const locale = await getLocale();
  const { api, isOwner } = await getPlatform();
  if (!isOwner) notFound();
  const page = Math.max(1, Number((await searchParams).page) || 1);
  const entries = unwrap(
    await api.GET("/platform/audit", { params: { query: { limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE } } }),
  );
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });
  const actions: Record<string, string> = (await getMessages()).platform.audit.actions;
  const label = (action: string) => actions[action.replace(".", "_")] ?? action;
  const detail = (details: Record<string, unknown>) =>
    Object.entries(details)
      .filter(([, value]) => value !== null && value !== "" && !(Array.isArray(value) && value.length === 0))
      .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : String(value)}`)
      .join(" · ");

  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader titleId="audit-heading" title={t("audit.title")} description={t("audit.subtitle")} />
      {entries.length === 0 ? (
        <EmptyState variant="list">{t("audit.empty")}</EmptyState>
      ) : (
        <ScrollRegion labelledBy="audit-heading" className="card">
          <table className="w-full text-sm">
            <thead className="bg-surface text-muted">
              <tr>
                {(["when", "who", "action", "business", "details"] as const).map((key) => (
                  <th key={key} scope="col" className="px-4 py-3 text-start font-medium">
                    {t(`audit.${key}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map((entry, index) => (
                <tr key={`${entry.occurred_at}-${index}`} className="border-t border-border align-top">
                  <td className="whitespace-nowrap px-4 py-2.5">{when.format(new Date(entry.occurred_at))}</td>
                  <td className="px-4 py-2.5" dir="ltr">{entry.actor_email}</td>
                  <td className="px-4 py-2.5 font-medium">{label(entry.action)}</td>
                  <td className="px-4 py-2.5" dir="auto">
                    {entry.tenant_id ? (
                      <Link href={`/platform/businesses/${entry.tenant_id}`} className="text-primary-ink underline-offset-4 hover:underline">
                        {entry.tenant_name}
                      </Link>
                    ) : (
                      "-"
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-muted" dir="ltr">{detail(entry.details)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      )}
      {(page > 1 || entries.length === PAGE_SIZE) && (
        <nav aria-label={t("audit.title")} className="flex items-center justify-between text-sm">
          {page > 1 ? <Link scroll={false} href={`/platform/audit?page=${page - 1}`} className="text-primary-ink">{t("audit.previous")}</Link> : <span />}
          {entries.length === PAGE_SIZE ? <Link scroll={false} href={`/platform/audit?page=${page + 1}`} className="text-primary-ink">{t("audit.next")}</Link> : <span />}
        </nav>
      )}
    </Container>
  );
}
