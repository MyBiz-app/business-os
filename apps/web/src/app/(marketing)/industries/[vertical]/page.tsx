import { ALL_VERTICALS, categories, childrenOf, vertical as findVertical, type Vertical } from "@business-os/verticals";
import { Check, Clock, CreditCard, IdCard, Users } from "lucide-react";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BRAND } from "@business-os/i18n/brand";

import { Section } from "@/components/layout/section";
import { CtaBand, FeatureGrid } from "@/components/marketing/sections";
import { SubpageHero } from "@/components/marketing/subpage";
import { VerticalIcon } from "@/components/vertical-icon";
import { formatMoney } from "@/lib/money";
import { industryTexts } from "@/lib/verticals";

export function generateStaticParams() {
  return ALL_VERTICALS.map(({ key }) => ({ vertical: key }));
}

export async function generateMetadata({ params }: PageProps<"/industries/[vertical]">): Promise<Metadata> {
  const { vertical } = await params;
  if (!findVertical(vertical)) return {};
  const { text } = industryTexts(await getTranslations());
  return { title: `${text(vertical, "name")} · ${BRAND.name}`, description: text(vertical, "heroText") };
}

/** One industry - a category, a sub-category or one coming soon: how MyBiz fits it. */
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
    <main id="main" className="enter flex flex-col">
      <SubpageHero
        lead={
          <span aria-hidden="true" className={`flex size-16 items-center justify-center rounded-3xl bg-gradient-to-br ${color} text-white shadow-xl`}>
            <VerticalIcon icon={icon} className="size-8" />
          </span>
        }
        eyebrow={
          <span className="flex flex-wrap items-center gap-2">
            {match.parent && (
              <>
                <Link href={`/industries/${match.category}`} className="underline-offset-4 hover:underline">
                  {text(match.category, "name")}
                </Link>
                <span aria-hidden="true">·</span>
              </>
            )}
            <span>{text(key, "name")}</span>
            {planned && <span className="rounded-full bg-warning/20 px-2.5 py-0.5 text-xs">{t("industries.soon")}</span>}
          </span>
        }
        title={text(key, "heroTitle")}
        description={planned ? t("industries.soonPage", { name: text(key, "name") }) : text(key, "heroText")}
        aside={
          <ul className="flex flex-col gap-3 rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur sm:p-8">
            {points(key).map((point) => (
              <li key={point} className="flex items-start gap-3 text-lg font-medium text-white/90">
                <Check aria-hidden="true" className="mt-1 size-5 shrink-0 text-electric" />
                {point}
              </li>
            ))}
          </ul>
        }
      >
        <div className="flex flex-wrap gap-3">
          {planned ? (
            <Link href={`/contact?vertical=${key}`} className="btn-primary btn-lg">
              {t("industries.notify")}
            </Link>
          ) : (
            <>
              <Link href={`/start?vertical=${key}`} className="btn-primary btn-lg">
                {t("hero.ctaPrimary")}
              </Link>
              <Link href={`/contact?vertical=${key}`} className="btn-lg inline-flex items-center justify-center rounded-full border border-white/25 px-7 font-semibold text-white transition-colors hover:bg-white/10">
                {t("cta.contact")}
              </Link>
            </>
          )}
        </div>
      </SubpageHero>

      {kinds.length > 0 && (
        <Section spacing="compact" aria-labelledby="kinds-heading" innerClassName="flex flex-col gap-4">
          <h2 id="kinds-heading" className="text-lg font-semibold">
            {t("industries.kinds", { name: text(match.category, "name") })}
          </h2>
          <ul className="flex flex-wrap gap-2">
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
        </Section>
      )}

      {!planned && <ReadySection match={match} />}

      {/* Named by its own heading, so it never collides with the footer's industries nav. */}
      <Section spacing="compact" tone="surface" innerClassName="flex flex-col gap-4">
      <h2 id="all-industries" className="text-lg font-semibold">
        {t("industries.all")}
      </h2>
      <nav aria-labelledby="all-industries" className="flex flex-wrap gap-2">
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
      </Section>

      <FeatureGrid />
      <CtaBand />
    </main>
  );
}

/** What a new business in this industry gets on day one, straight from the catalog: starter
 * services, plans and the client card's fields. */
async function ReadySection({ match }: { match: Vertical }) {
  const t = await getTranslations("marketing.industries.ready");
  const tFields = await getTranslations("clientFields");
  const { text } = industryTexts(await getTranslations());
  const locale = await getLocale();
  const lang = locale === "he" ? "he" : "en";
  const currency = locale === "he" ? "ILS" : "USD";
  // A category without its own services shows its first kind's.
  const firstKind = childrenOf(match.key).find((kind) => kind.defaultServices.length > 0);
  const services = (match.defaultServices.length ? match.defaultServices : (firstKind?.defaultServices ?? [])).slice(0, 4);
  const plans = match.defaultPlans.slice(0, 3);
  const fields = match.clientFields.slice(0, 5);
  if (!services.length && !plans.length && !fields.length) return null;

  const columns = [
    services.length > 0 && (
      <div key="services" className="card flex flex-col gap-4 p-6">
        <h3 className="flex items-center gap-2 font-semibold">
          <span aria-hidden="true" className="icon-tile size-9">
            <Clock className="size-4" />
          </span>
          {t("services")}
        </h3>
        <ul className="flex flex-col gap-2.5">
          {services.map((service) => (
            <li key={service.names.en} className="flex items-center justify-between gap-3 text-sm">
              <span className="flex items-center gap-2">
                <span aria-hidden="true" className="h-4 w-1 rounded-full" style={{ backgroundColor: service.color }} />
                {service.names[lang] ?? service.names.en}
              </span>
              <span className="flex items-center gap-2 text-muted">
                {service.capacity && service.capacity > 1 && (
                  <span className="flex items-center gap-1">
                    <Users aria-hidden="true" className="size-3.5" />
                    <span className="sr-only">{t("capacity")}</span>
                    {service.capacity}
                  </span>
                )}
                <span>{t("minutes", { count: service.duration_minutes })}</span>
                {service.prices[currency] !== undefined && (
                  <bdi className="font-semibold text-foreground">{formatMoney(service.prices[currency], currency, locale)}</bdi>
                )}
              </span>
            </li>
          ))}
        </ul>
      </div>
    ),
    plans.length > 0 && (
      <div key="plans" className="card flex flex-col gap-4 p-6">
        <h3 className="flex items-center gap-2 font-semibold">
          <span aria-hidden="true" className="icon-tile size-9">
            <CreditCard className="size-4" />
          </span>
          {t("plans")}
        </h3>
        <ul className="flex flex-col gap-2.5">
          {plans.map((plan) => (
            <li key={plan.names.en} className="flex items-center justify-between gap-3 text-sm">
              <span>{plan.names[lang] ?? plan.names.en}</span>
              <bdi className="font-semibold">{formatMoney(plan.prices[currency] ?? 0, currency, locale)}</bdi>
            </li>
          ))}
        </ul>
      </div>
    ),
    fields.length > 0 && (
      <div key="fields" className="card flex flex-col gap-4 p-6">
        <h3 className="flex items-center gap-2 font-semibold">
          <span aria-hidden="true" className="icon-tile size-9">
            <IdCard className="size-4" />
          </span>
          {t("fields", { client: text(match.key, "name") })}
        </h3>
        <ul className="flex flex-wrap gap-2">
          {fields.map((field) => (
            <li key={field.key} className="rounded-full bg-foreground/5 px-3 py-1 text-sm">
              {tFields(field.key as "goal")}
            </li>
          ))}
        </ul>
      </div>
    ),
  ].filter(Boolean);

  return (
    <Section tone="surface" aria-labelledby="ready-heading" innerClassName="flex flex-col gap-8">
      <div className="flex max-w-[44rem] flex-col gap-2">
        <h2 id="ready-heading" className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          {t("title")}
        </h2>
        <p className="text-lg text-muted">{t("subtitle")}</p>
      </div>
      <div className={`grid gap-4 ${columns.length === 3 ? "lg:grid-cols-3" : "md:grid-cols-2"}`}>{columns}</div>
      <p className="flex items-center gap-2 text-sm text-muted">
        <Check aria-hidden="true" className="size-4 text-success-ink" />
        {t("note")}
      </p>
    </Section>
  );
}
