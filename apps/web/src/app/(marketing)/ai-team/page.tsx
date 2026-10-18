import { Check } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Image from "next/image";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { Section } from "@/components/layout/section";
import { TeamOrg } from "@/components/marketing/ai-team-org";
import { TeamSim } from "@/components/marketing/ai-team-sim";
import { Reveal } from "@/components/marketing/reveal";
import { CtaBand, SectionHeading } from "@/components/marketing/sections";
import { BandText, SubpageHero } from "@/components/marketing/subpage";
import { CHIEF, PORTRAITS, SPECIALISTS } from "@/lib/ai-team";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("marketing.aiTeam");
  const tm = await getTranslations("marketing.meta");
  return { title: `${tm("aiTeam")} · ${BRAND.name}`, description: t("page.subtitle") };
}

/** The AI team page: every agent with what it does, the recorded simulation, hiring your own, and cost. */
export default async function AiTeamPage() {
  const t = await getTranslations("marketing.aiTeam");
  const hirePoints = t.raw("page.hirePoints") as string[];
  const costPoints = t.raw("page.costPoints") as string[];
  const ts = await getTranslations("marketing.aiTeam.sim");

  return (
    <main id="main" className="enter flex flex-col">
      <SubpageHero eyebrow={t("page.eyebrow")} title={t("page.title")} description={t("page.subtitle")}>
        <div className="flex flex-wrap gap-3">
          <Link href="/start" className="btn-primary btn-lg">
            {t("page.ctaPrimary")}
          </Link>
          <Link href="#simulation" className="btn-lg inline-flex items-center justify-center rounded-full border border-white/25 px-7 font-semibold text-white transition-colors hover:bg-white/10">
            {t("page.ctaSecondary")}
          </Link>
        </div>
      </SubpageHero>

      <Section aria-labelledby="org-heading" innerClassName="flex flex-col gap-10">
        <SectionHeading id="org-heading" eyebrow={t("home.eyebrow")} title={t("home.title")} subtitle={t("home.subtitle")} />
        <TeamOrg />
      </Section>

      <Section id="simulation" aria-labelledby="sim-heading" tone="surface" className="scroll-mt-20" innerClassName="flex flex-col gap-10">
        <SectionHeading id="sim-heading" eyebrow={ts("eyebrow")} title={ts("title")} subtitle={ts("subtitle")} />
        <div className="mx-auto w-full max-w-4xl">
          <TeamSim />
        </div>
      </Section>

      <Section aria-labelledby="agents-heading" innerClassName="flex flex-col gap-10">
        <SectionHeading id="agents-heading" title={t("page.teamTitle")} subtitle={t("page.teamSubtitle")} />
        <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {([CHIEF, ...SPECIALISTS] as const).map((agent, index) => (
            <li key={agent}>
              <Reveal delay={(index % 3) * 70} className="h-full">
                <article className="card flex h-full flex-col gap-4 p-6">
                  <div className="flex items-center gap-4">
                    <Image src={PORTRAITS[agent]} alt="" width={64} height={64} className="size-16 rounded-full object-cover ring-2 ring-border" />
                    <div className="flex flex-col">
                      <h3 className="text-lg font-bold">{t(`agents.${agent}.name`)}</h3>
                      <p className="text-sm text-muted">{t(`agents.${agent}.role`)}</p>
                    </div>
                  </div>
                  <p>{t(`agents.${agent}.does`)}</p>
                  <div className="mt-auto flex flex-col gap-2">
                    <p className="text-xs font-semibold text-muted">{t("page.exampleLabel")}</p>
                    <ul className="flex flex-col gap-2">
                      {(t.raw(`agents.${agent}.examples`) as string[]).map((example) => (
                        <li key={example} className="rounded-xl bg-foreground/5 px-3 py-2 text-sm">{example}</li>
                      ))}
                    </ul>
                  </div>
                </article>
              </Reveal>
            </li>
          ))}
        </ul>
      </Section>

      <Section tone="surface" innerClassName="grid items-start gap-12 lg:grid-cols-2">
        <Reveal>
          <BandText title={t("page.hireTitle")} text={t("page.hireText")}>
            <ul className="mt-2 flex flex-col gap-2">
              {hirePoints.map((point) => (
                <li key={point} className="flex items-center gap-2 font-medium">
                  <Check aria-hidden="true" className="size-5 text-success-ink" />
                  {point}
                </li>
              ))}
            </ul>
          </BandText>
        </Reveal>
        <Reveal delay={100}>
          <BandText title={t("page.costTitle")} text={t("page.costText")}>
            <ul className="mt-2 flex flex-col gap-2">
              {costPoints.map((point) => (
                <li key={point} className="flex items-center gap-2 font-medium">
                  <Check aria-hidden="true" className="size-5 text-success-ink" />
                  {point}
                </li>
              ))}
            </ul>
          </BandText>
        </Reveal>
      </Section>
      <CtaBand />
    </main>
  );
}
