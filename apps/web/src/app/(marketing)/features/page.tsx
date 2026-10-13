import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { BRAND } from "@business-os/i18n/brand";

import { Section } from "@/components/layout/section";
import { ChatMock, DashboardMock, PhoneMock } from "@/components/marketing/mocks";
import { BandText, SubpageHero } from "@/components/marketing/subpage";
import { BranchesSection, CtaBand, FeatureGrid, SafetySection } from "@/components/marketing/sections";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("marketing.meta");
  return { title: `${t("features")} · ${BRAND.name}` };
}

export default async function FeaturesPage() {
  const t = await getTranslations("marketing");
  return (
    <main className="enter flex flex-col">
      <SubpageHero title={t("features.title")} description={t("features.subtitle")} aside={<DashboardMock />} />
      <FeatureGrid inFeaturesPage />
      <Section tone="surface" innerClassName="grid items-center gap-12 lg:grid-cols-2">
        <BandText eyebrow={t("ai.eyebrow")} title={t("ai.title")} text={t("ai.text")} />
        <ChatMock question={t("ai.q")} answer={t("ai.a")} />
      </Section>
      <Section innerClassName="grid items-center gap-12 lg:grid-cols-2">
        <PhoneMock />
        <BandText eyebrow={t("app.eyebrow")} title={t("app.title")} text={t("app.text")} />
      </Section>
      <BranchesSection />
      <SafetySection />
      <CtaBand />
    </main>
  );
}
