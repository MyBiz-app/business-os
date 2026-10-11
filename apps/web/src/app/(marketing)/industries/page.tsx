import { categories, childrenOf } from "@business-os/verticals";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { CtaBand, SectionHeading } from "@/components/marketing/sections";
import { VerticalIcon } from "@/components/vertical-icon";
import { industryTexts } from "@/lib/verticals";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("marketing.industries");
  return { title: `${t("title")} · ${BRAND.name}`, description: t("subtitle") };
}

/** Every industry: the open categories with their kinds of business, then the ones coming soon. */
export default async function IndustriesPage() {
  const t = await getTranslations("marketing.industries");
  const { text } = industryTexts(await getTranslations());
  const open = categories().filter((c) => c.status !== "planned");
  const soon = categories().filter((c) => c.status === "planned");

  return (
    <main className="enter mx-auto flex w-full max-w-6xl flex-col gap-12 px-6 py-16">
      <SectionHeading level={1} title={t("title")} subtitle={t("subtitle")} />
      <ul className="grid gap-4 md:grid-cols-2">
        {open.map(({ key, icon, color }) => (
          <li key={key} className="card flex flex-col gap-4 p-6">
            <Link href={`/industries/${key}`} className="group flex items-center gap-4">
              <span aria-hidden="true" className={`flex size-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br ${color} text-white shadow-lg`}>
                <VerticalIcon icon={icon} className="size-6" />
              </span>
              <span className="flex flex-col">
                <span className="text-lg font-semibold group-hover:text-primary">{text(key, "name")}</span>
                <span className="text-sm text-muted">{text(key, "tagline")}</span>
              </span>
            </Link>
            <ul aria-label={t("kinds", { name: text(key, "name") })} className="flex flex-wrap gap-2">
              {childrenOf(key).map((kind) => (
                <li key={kind.key}>
                  <Link href={`/industries/${kind.key}`} className="block rounded-full bg-background px-3 py-1.5 text-sm ring-1 ring-border hover:ring-primary">
                    {text(kind.key, "name")}
                  </Link>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>

      {soon.length > 0 && (
        <section aria-labelledby="soon-heading" className="flex flex-col gap-6">
          <SectionHeading id="soon-heading" title={t("soonTitle")} subtitle={t("soonText")} />
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {soon.map(({ key, icon }) => (
              <li key={key}>
                <Link href={`/industries/${key}`} className="card card-hover flex h-full flex-col gap-2 p-5">
                  <VerticalIcon icon={icon} className="size-6 text-muted" />
                  <span className="font-semibold">{text(key, "name")}</span>
                  <span className="text-sm text-muted">{text(key, "tagline")}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
      <CtaBand />
    </main>
  );
}
