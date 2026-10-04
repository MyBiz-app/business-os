import { Check } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { CtaBand, FeatureGrid, INDUSTRIES, type IndustryKey } from "@/components/marketing/sections";

export function generateStaticParams() {
  return INDUSTRIES.map(({ key }) => ({ vertical: key }));
}

function industry(vertical: string) {
  return INDUSTRIES.find(({ key }) => key === vertical);
}

export async function generateMetadata({ params }: PageProps<"/industries/[vertical]">): Promise<Metadata> {
  const { vertical } = await params;
  if (!industry(vertical)) return {};
  const t = await getTranslations("marketing.industries.items");
  return { title: `${t(`${vertical as IndustryKey}.name`)} · MyBiz`, description: t(`${vertical as IndustryKey}.heroText`) };
}

/** One industry: how MyBiz fits it, and links to the others. */
export default async function IndustryPage({ params }: PageProps<"/industries/[vertical]">) {
  const { vertical } = await params;
  const match = industry(vertical);
  if (!match) notFound();
  const t = await getTranslations("marketing");
  const key = match.key;
  const Icon = match.Icon;

  return (
    <main className="enter flex flex-col">
      <section className="relative overflow-hidden">
        <div aria-hidden="true" className={`pointer-events-none absolute -top-32 -end-32 size-[28rem] rounded-full bg-gradient-to-br ${match.color} opacity-20 blur-3xl`} />
        <div className="relative mx-auto flex max-w-4xl flex-col items-center gap-6 px-6 py-20 text-center">
          <span aria-hidden="true" className={`flex size-16 items-center justify-center rounded-3xl bg-gradient-to-br ${match.color} text-white shadow-xl`}>
            <Icon className="size-8" />
          </span>
          <p className="text-sm font-semibold text-primary">{t(`industries.items.${key}.name`)}</p>
          <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl">{t(`industries.items.${key}.heroTitle`)}</h1>
          <p className="max-w-2xl text-lg text-muted">{t(`industries.items.${key}.heroText`)}</p>
          <ul className="flex flex-wrap justify-center gap-3">
            {(t.raw(`industries.items.${key}.points`) as string[]).map((point) => (
              <li key={point} className="flex items-center gap-2 rounded-full bg-surface px-4 py-2 text-sm font-medium shadow-sm ring-1 ring-border">
                <Check aria-hidden="true" className="size-4 text-success" />
                {point}
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap justify-center gap-3">
            <Link href="/signup" className="btn-primary px-6 py-3 text-lg">
              {t("hero.ctaPrimary")}
            </Link>
            <Link href="/contact" className="btn-secondary px-6 py-3 text-lg">
              {t("cta.contact")}
            </Link>
          </div>
        </div>
      </section>

      <nav aria-label={t("nav.industries")} className="mx-auto flex flex-wrap justify-center gap-2 px-6">
        {INDUSTRIES.map((other) => (
          <Link
            key={other.key}
            href={`/industries/${other.key}`}
            aria-current={other.key === key ? "page" : undefined}
            className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
              other.key === key ? "bg-primary text-on-primary" : "bg-surface ring-1 ring-border hover:ring-primary"
            }`}
          >
            {t(`industries.items.${other.key}.name`)}
          </Link>
        ))}
      </nav>

      <FeatureGrid />
      <CtaBand />
    </main>
  );
}
