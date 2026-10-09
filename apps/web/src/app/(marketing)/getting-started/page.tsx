import { ArrowRight, Check, Clock, LifeBuoy } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { SETUP_STEPS, type SetupStep } from "@/components/getting-started";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("gettingStarted.page");
  return { title: `${t("metaTitle")} · ${BRAND.name}`, description: t("metaDescription") };
}

type Section = { key: SetupStep; minutes: number; tips: string[] };

/** The public getting-started guide (linked from the welcome email and the dashboard). */
export default async function GettingStartedPage() {
  const t = await getTranslations("gettingStarted");
  const sections = t.raw("page.sections") as Section[];

  return (
    <main className="enter flex flex-col">
      <section className="mx-auto flex max-w-3xl flex-col items-center gap-4 px-6 pb-6 pt-16 text-center">
        <p className="text-sm font-semibold text-primary">{t("page.eyebrow")}</p>
        <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl">{t("page.title")}</h1>
        <p className="text-lg text-muted">{t("page.subtitle")}</p>
      </section>

      <ol className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-6 py-10">
        {sections.map((section, index) => {
          const { href, Icon } = SETUP_STEPS[section.key];
          return (
            <li key={section.key} className="card flex flex-col gap-4 p-6 sm:flex-row sm:gap-6">
              <div className="flex items-center gap-3 sm:flex-col sm:items-center">
                <span aria-hidden="true" className="btn-primary size-11 text-lg">
                  {index + 1}
                </span>
                <span aria-hidden="true" className="icon-tile size-11">
                  <Icon className="size-5" />
                </span>
              </div>
              <div className="flex flex-1 flex-col gap-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-xl font-bold">{t(`steps.${section.key}.title`)}</h2>
                  <span className="flex items-center gap-1 text-sm text-muted">
                    <Clock aria-hidden="true" className="size-4" />
                    {t("page.minutes", { count: section.minutes })}
                  </span>
                </div>
                <p className="text-muted">{t(`steps.${section.key}.text`)}</p>
                <ul className="flex flex-col gap-2">
                  {section.tips.map((tip) => (
                    <li key={tip} className="flex items-start gap-2">
                      <Check aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-success" />
                      {tip}
                    </li>
                  ))}
                </ul>
                <Link href={href} className="flex items-center gap-1.5 self-start font-semibold text-primary underline-offset-4 hover:underline">
                  {t("page.openInApp")}
                  <ArrowRight aria-hidden="true" className="size-4 rtl:rotate-180" />
                </Link>
              </div>
            </li>
          );
        })}
      </ol>

      <section className="mx-auto mb-16 flex w-full max-w-3xl flex-col items-center gap-3 px-6 text-center">
        <span aria-hidden="true" className="icon-tile size-12">
          <LifeBuoy className="size-6" />
        </span>
        <h2 className="text-2xl font-bold">{t("page.helpTitle")}</h2>
        <p className="text-muted">{t("page.helpText")}</p>
        <div className="flex flex-wrap justify-center gap-3">
          <Link href="/contact" className="btn-primary px-5 py-3">
            {t("page.helpCta")}
          </Link>
          <Link href="/start" className="btn-secondary px-5 py-3">
            {t("page.startCta")}
          </Link>
        </div>
      </section>
    </main>
  );
}
