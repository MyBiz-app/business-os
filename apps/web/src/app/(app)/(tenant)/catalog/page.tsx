import { Plus } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { FormNotice } from "@/components/form/form-message";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { LinkSegmented } from "@/components/ui/link-segmented";
import { canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { CodesTab } from "./codes-tab";
import { PlansTab } from "./plans-tab";
import { ServicesTab } from "./services-tab";
import { catalogHref, SHOWS, tabOrder } from "./tabs";

const ADD_HREF = { services: "/catalog/services/new", plans: "/catalog/plans/new", codes: "/catalog/promos/new" } as const;

/** Services, memberships and punch cards, and discount codes in one place. The tab and the filter
 * live in the address (`/catalog?tab=plans&show=active`). */
export default async function CatalogPage({ searchParams }: PageProps<"/catalog">) {
  const params = await searchParams;
  const t = await getTranslations();
  const { tenant } = await getTenantFor("catalog.read");
  const order = tabOrder(tenant.booking_requires_plan);
  const tab = order.find((key) => key === params.tab) ?? order[0];
  const show = SHOWS.find((key) => key === params.show) ?? "all";
  const removed = typeof params.removed === "string" ? params.removed : undefined;
  const removedKey = removed && ["deleted", "archived"].includes(removed) ? removed : undefined;

  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      {removedKey && tab !== "codes" && <FormNotice message={t(`${tab}.removed.${removedKey}` as "plans.removed.deleted")} />}
      {removed === "code" && <FormNotice message={t("promo.removed")} />}
      <PageHeader
        title={t("catalog.title")}
        description={t("catalog.subtitle")}
        actions={
          canWriteCatalog(tenant) && (
            <Link href={ADD_HREF[tab]} scroll={false} className="btn-primary px-4 py-2.5">
              <Plus aria-hidden="true" className="size-4" /> {t(`catalog.add.${tab}`)}
            </Link>
          )
        }
      />
      <LinkSegmented
        label={t("catalog.tabs.label")}
        loadingLabel={t("common.loading")}
        active={tab}
        options={order.map((key) => ({ key, label: t(`catalog.tabs.${key}`), href: catalogHref(key) }))}
      />
      {tab === "plans" && <PlansTab show={show} />}
      {tab === "services" && <ServicesTab show={show} />}
      {tab === "codes" && <CodesTab show={show} />}
    </Container>
  );
}
