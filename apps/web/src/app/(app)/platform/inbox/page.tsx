import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { unwrap } from "@/lib/api";
import { getPlatformFor } from "@/lib/platform";

import { RequestCard } from "./request-card";

const FILTERS = ["open", "all", "business", "site"] as const;
type Filter = (typeof FILTERS)[number];

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("platform.inbox");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** The console's inbox: requests from the website and messages from businesses. */
export default async function PlatformInboxPage({ searchParams }: PageProps<"/platform/inbox">) {
  const t = await getTranslations("platform.inbox");
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
    <main className="enter mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <p className="text-muted">{t("subtitle")}</p>
      </div>
      <nav aria-label={t("filter")} className="flex flex-wrap gap-1 rounded-xl border border-border bg-surface p-1 text-sm shadow-sm">
        {FILTERS.map((value) => (
          <Link
            key={value}
            href={`/platform/inbox?show=${value}`}
            aria-current={value === filter ? "page" : undefined}
            className={`rounded-lg px-3 py-1.5 font-medium ${value === filter ? "bg-primary text-on-primary" : "hover:bg-foreground/5"}`}
          >
            {labels[value]}
          </Link>
        ))}
      </nav>
      <p className="text-sm text-muted">{t("count", { count: requests.length })}</p>
      {requests.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border p-10 text-center text-muted">{t("empty")}</p>
      ) : (
        <ul className="enter-items flex flex-col gap-3">
          {requests.map((request) => (
            <RequestCard key={`${request.id}-${request.status}-${request.assignee}`} request={request} when={when.format(new Date(request.created_at))} />
          ))}
        </ul>
      )}
    </main>
  );
}
