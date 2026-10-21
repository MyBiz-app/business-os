import { BRAND } from "@business-os/i18n/brand";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";

import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { getPlatformFor } from "@/lib/platform";

import { OpenIncidentForm, ResolveButton } from "./incident-form";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("platform.incidents");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** Incident banners: open one when something is wrong (or planned), resolve it when it is over. */
export default async function IncidentsPage() {
  const t = await getTranslations("platform.incidents");
  const locale = await getLocale();
  const { api } = await getPlatformFor("incidents.manage");
  const items = unwrap(await api.GET("/platform/incidents"));
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });

  return (
    <Container as="main" size="settings" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader title={t("title")} description={t("subtitle")} />
      <OpenIncidentForm />
      {items.length === 0 ? (
        <EmptyState variant="inbox">{t("empty")}</EmptyState>
      ) : (
        <ul className="enter-items flex flex-col gap-3">
          {items.map((item) => {
            const texts = item.content.he?.title ? item.content.he : item.content.en;
            return (
              <li key={item.id} className="flex flex-wrap items-center gap-3 card p-4 sm:p-5">
                <span className="flex min-w-0 flex-1 flex-col gap-1">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold" dir="auto">
                      {texts?.title}
                    </span>
                    <Pill tone={item.resolved_at ? "success" : "warning"}>{item.resolved_at ? t("resolved") : t("openNow")}</Pill>
                    <Pill tone="muted">{t(`kinds.${item.kind}`)}</Pill>
                  </span>
                  <span className="text-sm text-muted">
                    {when.format(new Date(item.created_at))} · {item.created_by}
                  </span>
                </span>
                {!item.resolved_at && <ResolveButton id={item.id} />}
              </li>
            );
          })}
        </ul>
      )}
    </Container>
  );
}
