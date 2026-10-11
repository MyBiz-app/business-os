import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { BRAND } from "@business-os/i18n/brand";

import { CtaBand } from "@/components/marketing/sections";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("marketing.meta");
  return { title: `${t("about")} · ${BRAND.name}` };
}

export default async function AboutPage() {
  const t = await getTranslations("marketing.about");
  const values = t.raw("values") as { title: string; text: string }[];
  return (
    <main className="enter flex flex-col">
      <section className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-20 text-center">
        <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl">{t("title")}</h1>
        <p className="text-xl leading-relaxed text-muted">{t("intro")}</p>
      </section>
      <section aria-labelledby="values-heading" className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-6 pb-10">
        <h2 id="values-heading" className="text-center text-2xl font-bold">
          {t("valuesTitle")}
        </h2>
        <ul className="enter-items grid gap-4 sm:grid-cols-2">
          {values.map((value) => (
            <li key={value.title} className="card card-hover flex flex-col gap-2 p-6">
              <h3 className="text-lg font-semibold">{value.title}</h3>
              <p className="text-muted">{value.text}</p>
            </li>
          ))}
        </ul>
      </section>
      <CtaBand />
    </main>
  );
}
