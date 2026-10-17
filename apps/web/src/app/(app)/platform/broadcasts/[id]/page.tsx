import { notFound } from "next/navigation";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Pill } from "@/components/pill";
import { getPlatformFor } from "@/lib/platform";

import { ComposerPage } from "../composer-page";

/** A draft or scheduled message opens in the editor; one that already went out shows its results. */
export default async function BroadcastPage({ params }: PageProps<"/platform/broadcasts/[id]">) {
  const { id } = await params;
  const { api } = await getPlatformFor("broadcasts.manage");
  const { data: item } = await api.GET("/platform/broadcasts/{announcement_id}", { params: { path: { announcement_id: id } } });
  if (!item) notFound();
  if (item.status === "draft" || item.status === "scheduled") return <ComposerPage announcement={item} />;

  const t = await getTranslations("platform.broadcasts");
  const locale = await getLocale();
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });
  const rows: [string, number][] = [
    [t("results.recipients"), item.recipient_count ?? 0],
    [t("results.sent"), item.stats.sent],
    [t("results.failed"), item.stats.failed],
    [t("results.skipped"), item.stats.skipped],
    [t("results.viewed"), item.stats.viewed],
    [t("results.clicked"), item.stats.clicked],
    [t("results.unsubscribed"), item.stats.unsubscribed],
  ];
  const subject = item.content.he?.subject || item.content.en?.subject || "";

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <Link href="/platform/broadcasts" className="text-sm font-medium text-primary-ink hover:underline">
        {t("back")}
      </Link>
      <PageHeader title={subject || t("title")} description={`${item.audience.groups.map((g) => t(`groups.${g}`)).join(" · ")} | ${item.channels.map((c) => t(`channels.${c}`)).join(" · ")}`} />
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <Pill tone={item.status === "sent" ? "success" : item.status === "sending" ? "warning" : "muted"}>{t(`statuses.${item.status}`)}</Pill>
        <span className="text-muted">
          {t("created", { name: item.created_by })} · {when.format(new Date(item.sent_at ?? item.created_at))}
        </span>
      </p>
      <section aria-labelledby="results-title" className="flex flex-col gap-3 rounded-2xl border border-border p-4">
        <h2 id="results-title" className="font-semibold">
          {t("results.title")}
        </h2>
        <dl className="grid gap-3 sm:grid-cols-3">
          {rows.map(([label, value]) => (
            <div key={label} className="rounded-xl bg-surface p-3 shadow-sm ring-1 ring-border">
              <dt className="text-xs text-muted">{label}</dt>
              <dd className="text-2xl font-semibold">{value}</dd>
            </div>
          ))}
        </dl>
        <p className="text-xs text-muted">{t("results.note")}</p>
      </section>
    </Container>
  );
}
