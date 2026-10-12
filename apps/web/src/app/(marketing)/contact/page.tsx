import { isVertical } from "@business-os/verticals";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { BRAND } from "@business-os/i18n/brand";

import { PageHero } from "@/components/marketing/sections";
import { ContactForm } from "./contact-form";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("marketing.meta");
  return { title: `${t("contact")} · ${BRAND.name}` };
}

export default async function ContactPage({ searchParams }: PageProps<"/contact">) {
  const t = await getTranslations("marketing.contact");
  const { vertical } = await searchParams;
  return (
    <main className="enter flex flex-col">
      <PageHero title={t("title")} subtitle={t("subtitle")} />
      <section className="card relative mx-auto my-12 w-full max-w-2xl p-6 sm:p-8">
        <ContactForm vertical={typeof vertical === "string" && isVertical(vertical) ? vertical : undefined} />
      </section>
    </main>
  );
}
