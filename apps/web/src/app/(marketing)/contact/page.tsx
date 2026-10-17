import { isVertical } from "@business-os/verticals";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { BRAND } from "@business-os/i18n/brand";

import { Check } from "lucide-react";

import { Section } from "@/components/layout/section";
import { Reveal } from "@/components/marketing/reveal";
import { SubpageHero } from "@/components/marketing/subpage";
import { ContactForm } from "./contact-form";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("marketing.meta");
  return { title: `${t("contact")} · ${BRAND.name}` };
}

export default async function ContactPage({ searchParams }: PageProps<"/contact">) {
  const t = await getTranslations("marketing.contact");
  const { vertical } = await searchParams;
  const points = t.raw("points") as string[];
  return (
    <main id="main" className="enter flex flex-col">
      <SubpageHero title={t("title")} description={t("subtitle")}>
        <ul className="flex flex-col gap-3">
          {points.map((point, index) => (
            <li key={point} style={{ animationDelay: `${300 + index * 150}ms` }} className="mk-rise flex items-start gap-3 font-medium text-white/90">
              <Check aria-hidden="true" className="mk-pulse mt-0.5 size-5 shrink-0 rounded-full text-electric" />
              {point}
            </li>
          ))}
        </ul>
      </SubpageHero>
      <Section size="default" spacing="compact">
        <Reveal className="card mk-shine relative mx-auto w-full max-w-[55rem] p-6 sm:p-10">
          <ContactForm vertical={typeof vertical === "string" && isVertical(vertical) ? vertical : undefined} />
        </Reveal>
      </Section>
    </main>
  );
}
