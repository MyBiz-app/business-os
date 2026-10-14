import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { BRAND } from "@business-os/i18n/brand";

import { Section } from "@/components/layout/section";
import { CtaBand } from "@/components/marketing/sections";
import { Reveal } from "@/components/marketing/reveal";
import { SubpageHero } from "@/components/marketing/subpage";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("marketing.meta");
  return { title: `${t("about")} · ${BRAND.name}` };
}

export default async function AboutPage() {
  const t = await getTranslations("marketing.about");
  const values = t.raw("values") as { title: string; text: string }[];
  return (
    <main className="enter flex flex-col">
      <SubpageHero title={t("title")} description={t("intro")} />
      <Section aria-labelledby="values-heading" innerClassName="flex flex-col gap-10">
        <h2 id="values-heading" className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          {t("valuesTitle")}
        </h2>
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {values.map((value, index) => (
            <li key={value.title}>
              <Reveal delay={index * 90} className="card card-hover mk-shine flex h-full flex-col gap-3 p-6">
              <span aria-hidden="true" className="icon-tile mk-pulse size-10 text-base font-bold">
                {index + 1}
              </span>
              <h3 className="text-lg font-semibold">{value.title}</h3>
              <p className="text-muted">{value.text}</p>
              </Reveal>
            </li>
          ))}
        </ul>
      </Section>
      <CtaBand />
    </main>
  );
}
