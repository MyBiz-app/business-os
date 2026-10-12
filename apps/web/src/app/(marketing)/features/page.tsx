import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { BRAND } from "@business-os/i18n/brand";

import { ChatMock, DashboardMock, PhoneMock } from "@/components/marketing/mocks";
import { BranchesSection, CtaBand, FeatureGrid, PageHero, SafetySection, SectionHeading } from "@/components/marketing/sections";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("marketing.meta");
  return { title: `${t("features")} · ${BRAND.name}` };
}

export default async function FeaturesPage() {
  const t = await getTranslations("marketing");
  return (
    <main className="enter flex flex-col">
      <PageHero title={t("features.title")} subtitle={t("features.subtitle")} />
      <section className="mx-auto flex w-full max-w-6xl flex-col gap-12 px-6 pt-16">
        <DashboardMock />
      </section>
      <FeatureGrid inFeaturesPage />
      <section className="bg-surface/60 py-20">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 lg:grid-cols-2">
          <div className="flex flex-col gap-4">
            <SectionHeading eyebrow={t("ai.eyebrow")} title={t("ai.title")} subtitle={t("ai.text")} />
          </div>
          <ChatMock question={t("ai.q")} answer={t("ai.a")} />
        </div>
      </section>
      <section className="py-20">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 lg:grid-cols-2">
          <PhoneMock />
          <SectionHeading eyebrow={t("app.eyebrow")} title={t("app.title")} subtitle={t("app.text")} />
        </div>
      </section>
      <BranchesSection />
      <SafetySection />
      <CtaBand />
    </main>
  );
}
