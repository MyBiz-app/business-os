import { ALL_VERTICALS, categories, childrenOf, vertical as findVertical } from "@business-os/verticals";
import { Check } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { CtaBand, FeatureGrid } from "@/components/marketing/sections";
import { VerticalIcon } from "@/components/vertical-icon";
import { industryTexts } from "@/lib/verticals";

export function generateStaticParams() {
  return ALL_VERTICALS.map(({ key }) => ({ vertical: key }));
}

export async function generateMetadata({ params }: PageProps<"/industries/[vertical]">): Promise<Metadata> {
  const { vertical } = await params;
  if (!findVertical(vertical)) return {};
  const { text } = industryTexts(await getTranslations());
  return { title: `${text(vertical, "name")} · MyBiz`, description: text(vertical, "heroText") };
}

/** One industry — a category, a sub-category or one coming soon: how MyBiz fits it. */
export default async function IndustryPage({ params }: PageProps<"/industries/[vertical]">) {
  const { vertical } = await params;
  const match = findVertical(vertical);
  if (!match) notFound();
  const t = await getTranslations("marketing");
  const { text, points } = industryTexts(await getTranslations());
  const { key, icon, color } = match;
  const planned = match.status === "planned";
  const kinds = childrenOf(match.depth === 0 ? key : match.category);

  return (
    <main className="enter flex flex-col">
      <section className="relative overflow-hidden">
        <div aria-hidden="true" className={`pointer-events-none absolute -top-32 -end-32 size-[28rem] rounded-full bg-gradient-to-br ${color} opacity-20 blur-3xl`} />
        <div className="relative mx-auto flex max-w-4xl flex-col items-center gap-6 px-6 py-20 text-center">
          <span aria-hidden="true" className={`flex size-16 items-center justify-center rounded-3xl bg-gradient-to-br ${color} text-white shadow-xl`}>
            <VerticalIcon icon={icon} className="size-8" />
          </span>
          <p className="flex flex-wrap items-center justify-center gap-2 text-sm font-semibold text-primary">
            {match.parent && (
              <>
                <Link href={`/industries/${match.category}`} className="underline-offset-4 hover:underline">
                  {text(match.category, "name")}
                </Link>
                <span aria-hidden="true">·</span>
              </>
            )}
            <span>{text(key, "name")}</span>
            {planned && <span className="rounded-full bg-warning/15 px-2.5 py-0.5 text-xs text-foreground">{t("industries.soon")}</span>}
          </p>
          <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl">{text(key, "heroTitle")}</h1>
          <p className="max-w-2xl text-lg text-muted">{planned ? t("industries.soonPage", { name: text(key, "name") }) : text(key, "heroText")}</p>
          <ul className="flex flex-wrap justify-center gap-3">
            {points(key).map((point) => (
              <li key={point} className="flex items-center gap-2 rounded-full bg-surface px-4 py-2 text-sm font-medium shadow-sm ring-1 ring-border">
                <Check aria-hidden="true" className="size-4 text-success" />
                {point}
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap justify-center gap-3">
            {planned ? (
              <Link href={`/contact?vertical=${key}`} className="btn-primary px-6 py-3 text-lg">
                {t("industries.notify")}
              </Link>
            ) : (
              <>
                <Link href={`/start?vertical=${key}`} className="btn-primary px-6 py-3 text-lg">
                  {t("hero.ctaPrimary")}
                </Link>
                <Link href={`/contact?vertical=${key}`} className="btn-secondary px-6 py-3 text-lg">
                  {t("cta.contact")}
                </Link>
              </>
            )}
          </div>
        </div>
      </section>

      {kinds.length > 0 && (
        <section aria-labelledby="kinds-heading" className="mx-auto flex w-full max-w-4xl flex-col items-center gap-4 px-6 pb-10">
          <h2 id="kinds-heading" className="text-lg font-semibold">
            {t("industries.kinds", { name: text(match.category, "name") })}
          </h2>
          <ul className="flex flex-wrap justify-center gap-2">
            {kinds.map((kind) => (
              <li key={kind.key}>
                <Link
                  href={`/industries/${kind.key}`}
                  aria-current={kind.key === key ? "page" : undefined}
                  className={`block rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                    kind.key === key ? "bg-primary text-on-primary" : "bg-surface ring-1 ring-border hover:ring-primary"
                  }`}
                >
                  {text(kind.key, "name")}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <nav aria-label={t("nav.industries")} className="mx-auto flex flex-wrap justify-center gap-2 px-6">
        {categories().map((other) => (
          <Link
            key={other.key}
            href={`/industries/${other.key}`}
            aria-current={other.key === match.category ? "true" : undefined}
            className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
              other.key === match.category ? "bg-primary text-on-primary" : "bg-surface ring-1 ring-border hover:ring-primary"
            }`}
          >
            {text(other.key, "name")}
          </Link>
        ))}
      </nav>

      <FeatureGrid />
      <CtaBand />
    </main>
  );
}
