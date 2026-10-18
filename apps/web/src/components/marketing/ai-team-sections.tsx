import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Image from "next/image";

import { Section } from "@/components/layout/section";
import { TeamOrg } from "@/components/marketing/ai-team-org";
import { TeamSim } from "@/components/marketing/ai-team-sim";
import { Reveal } from "@/components/marketing/reveal";
import { SectionHeading } from "@/components/marketing/sections";
import { PORTRAITS, type TeamKey } from "@/lib/ai-team";

/** The home page's AI team band: the org chart (single business or branch network) and the
 * recorded simulation, then a link to the full page. */
export async function AiTeamSection() {
  const t = await getTranslations("marketing.aiTeam");
  const ts = await getTranslations("marketing.aiTeam.sim");
  return (
    <>
      <Section id="ai-team" aria-labelledby="ai-team-heading" className="scroll-mt-20" innerClassName="flex flex-col gap-10">
        <Reveal>
          <SectionHeading id="ai-team-heading" eyebrow={t("home.eyebrow")} title={t("home.title")} subtitle={t("home.subtitle")} />
        </Reveal>
        <TeamOrg />
      </Section>
      <Section id="ai-team-demo" aria-labelledby="ai-team-demo-heading" className="scroll-mt-20 !pt-0" innerClassName="flex flex-col gap-10">
        <Reveal>
          <SectionHeading id="ai-team-demo-heading" eyebrow={ts("eyebrow")} title={ts("title")} subtitle={ts("subtitle")} />
        </Reveal>
        <Reveal className="mx-auto w-full max-w-4xl">
          <TeamSim />
        </Reveal>
        <Link href="/ai-team" className="group mx-auto inline-flex items-center gap-1 font-semibold text-primary-ink">
          {t("home.more")}
          <ArrowLeft aria-hidden="true" className="size-4 transition-transform group-hover:-translate-x-1 ltr:rotate-180 ltr:group-hover:translate-x-1" />
        </Link>
      </Section>
    </>
  );
}

/** One line on a product or industry page: "your agent for this field", with the portrait. */
export async function AgentLine({ agent }: { agent: Exclude<TeamKey, "chief"> }) {
  const t = await getTranslations("marketing.aiTeam");
  const name = t(`agents.${agent}.name`);
  return (
    <Section spacing="compact" aria-label={t("line.label")}>
      <Reveal>
        <div className="card mx-auto flex max-w-3xl flex-col items-center gap-4 p-5 sm:flex-row">
          <Image src={PORTRAITS[agent]} alt="" width={72} height={72} className="size-[72px] shrink-0 rounded-full object-cover ring-2 ring-border" />
          <div className="flex flex-1 flex-col gap-1 text-center sm:text-start">
            <p className="text-sm font-semibold text-ai">{t("line.label")}</p>
            <p>
              <strong>{name}</strong>{`, ${t(`agents.${agent}.role`)}: ${t(`agents.${agent}.does`)}`}
            </p>
          </div>
          <Link href="/ai-team" className="btn-secondary shrink-0 rounded-full px-5 py-2.5 text-sm">
            {t("line.more")}
          </Link>
        </div>
      </Reveal>
    </Section>
  );
}
