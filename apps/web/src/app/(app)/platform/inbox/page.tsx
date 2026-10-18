import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { unwrap } from "@/lib/api";
import { getPlatformFor } from "@/lib/platform";

import { RequestCard } from "./request-card";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/empty-state";
import { LinkSegmented } from "@/components/ui/link-segmented";

const FILTERS = ["open", "all", "business", "site"] as const;
type Filter = (typeof FILTERS)[number];

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("platform.inbox");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** The console's inbox: requests from the website and messages from businesses. */
export default async function PlatformInboxPage({ searchParams }: PageProps<"/platform/inbox">) {
  const t = await getTranslations("platform.inbox");
  const tc = await getTranslations("common");
  const locale = await getLocale();
  const { api } = await getPlatformFor("inbox.manage");
  const requested = (await searchParams).show;
  const filter: Filter = (FILTERS as readonly string[]).includes(String(requested)) ? (requested as Filter) : "open";
  const all = unwrap(await api.GET("/platform/contact-requests"));
  const requests = all.filter((r) =>
    filter === "all" ? true : filter === "business" ? r.from_business : filter === "site" ? !r.from_business : r.status !== "done",
  );
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });
  const labels: Record<Filter, string> = {
    open: `${t("statuses.new")} · ${t("statuses.in_progress")}`,
    all: t("all"),
    business: t("fromBusiness"),
    site: t("fromSite"),
  };

  return (
    <Container as="main" size="settings" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader title={t("title")} description={t("subtitle")} />
      <div>
        <LinkSegmented
          label={t("filter")}
          loadingLabel={tc("loading")}
          active={filter}
          options={FILTERS.map((value) => ({ key: value, label: labels[value], href: `/platform/inbox?show=${value}` }))}
        />
      </div>
      <p className="text-sm text-muted">{t("count", { count: requests.length })}</p>
      {requests.length === 0 ? (
        <EmptyState variant="inbox">{t("empty")}</EmptyState>
      ) : (
        <ul className="enter-items flex flex-col gap-3">
          {requests.map((request) => (
            <RequestCard key={`${request.id}-${request.status}-${request.assignee}`} request={request} when={when.format(new Date(request.created_at))} />
          ))}
        </ul>
      )}
    </Container>
  );
}
