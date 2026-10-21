import { ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { getTenant } from "@/lib/tenant";
import { hasUpgrade, type Upgrade, UPGRADES } from "@/lib/upgrades";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("upgrade");
  return { title: `${t("indexTitle")} · ${BRAND.name}` };
}

/** Every capability the business doesn't have yet. The side menu links here once its grey items
 * fold into "Add capabilities" (30 days after the business was created). */
export default async function CapabilitiesPage() {
  const t = await getTranslations("upgrade");
  const tOffers = await getTranslations("start.offers");
  const { tenant } = await getTenant();
  const missing = (Object.keys(UPGRADES) as Upgrade[]).filter(
    (offer) => !hasUpgrade(tenant.modules, offer) && tenant.permissions.includes(UPGRADES[offer].permission),
  );

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader title={t("indexTitle")} description={t("indexIntro")} />
      {missing.length === 0 ? (
        <p className="text-muted">{t("indexAll")}</p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {missing.map((offer) => (
            <Card as="li" key={offer} interactive className="flex flex-col gap-2">
              <h2 className="text-lg font-semibold">{tOffers(`${offer}.title`)}</h2>
              <p className="flex-1 text-sm text-muted">{tOffers(`${offer}.text`)}</p>
              <Link href={`/upgrade/${offer}`} className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary-ink underline-offset-4 hover:underline">
                {t("learnMore")}
                <ArrowRight aria-hidden="true" className="size-4 rtl:-scale-x-100" />
              </Link>
            </Card>
          ))}
        </ul>
      )}
    </Container>
  );
}
