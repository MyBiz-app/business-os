import { isVertical } from "@business-os/verticals";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { BRAND } from "@business-os/i18n/brand";

import { ContactForm } from "./contact-form";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("marketing.meta");
  return { title: `${t("contact")} · ${BRAND.name}` };
}

export default async function ContactPage({ searchParams }: PageProps<"/contact">) {
  const t = await getTranslations("marketing.contact");
  const { vertical } = await searchParams;
  return (
    <main className="enter mx-auto flex w-full max-w-2xl flex-col gap-8 px-6 py-16">
      <div className="flex flex-col gap-3 text-center">
        <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl">{t("title")}</h1>
        <p className="text-lg text-muted">{t("subtitle")}</p>
      </div>
      <section className="card relative p-6 sm:p-8">
        <ContactForm vertical={typeof vertical === "string" && isVertical(vertical) ? vertical : undefined} />
      </section>
    </main>
  );
}
