import { BRAND } from "@business-os/i18n/brand";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Pill, type Tone } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { getPlatformFor } from "@/lib/platform";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("platform.broadcasts");
  return { title: `${t("title")} · ${BRAND.name}` };
}

const TONE: Record<string, Tone> = { draft: "muted", scheduled: "primary", sending: "warning", sent: "success", cancelled: "muted" };

/** The broadcast center: every message sent or waiting to be sent, and how it did. */
export default async function BroadcastsPage() {
  const t = await getTranslations("platform.broadcasts");
  const locale = await getLocale();
  const { api } = await getPlatformFor("broadcasts.manage");
  const items = unwrap(await api.GET("/platform/broadcasts"));
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader
        title={t("title")}
        description={t("subtitle")}
        actions={
          <Link href="/platform/broadcasts/new" className="btn-primary px-4 py-2.5">
            {t("new")}
          </Link>
        }
      />
      {items.length === 0 ? (
        <EmptyState variant="inbox">{t("empty")}</EmptyState>
      ) : (
        <ul className="enter-items flex flex-col gap-3">
          {items.map((item) => {
            const content = item.content.he?.subject || item.content.en?.subject || "";
            const date = item.sent_at ?? item.scheduled_at ?? item.created_at;
            return (
              <li key={item.id} className="rounded-xl border border-border bg-surface p-4 shadow-sm">
                <Link href={`/platform/broadcasts/${item.id}`} className="flex flex-col gap-2">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold" dir="auto">
                      {content || t("statuses.draft")}
                    </span>
                    <Pill tone={TONE[item.status] ?? "muted"}>{t(`statuses.${item.status}`)}</Pill>
                    <Pill tone={item.kind === "marketing" ? "primary" : "muted"}>{t(`kinds.${item.kind}`)}</Pill>
                  </span>
                  <span className="text-sm text-muted">
                    {item.audience.groups.map((g) => t(`groups.${g}`)).join(" · ")}
                    {" | "}
                    {item.channels.map((c) => t(`channels.${c}`)).join(" · ")}
                    {" | "}
                    {when.format(new Date(date))}
                  </span>
                  {item.status !== "draft" && item.status !== "cancelled" && (
                    <span className="text-sm">
                      {t("results.sent")}: {item.stats.sent} · {t("results.viewed")}: {item.stats.viewed} · {t("results.clicked")}: {item.stats.clicked} · {t("results.unsubscribed")}: {item.stats.unsubscribed}
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Container>
  );
}
