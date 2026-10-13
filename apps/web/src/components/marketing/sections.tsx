import {
  ArrowLeft,
  BarChart3,
  Bot,
  CalendarDays,
  Check,
  CalendarClock,
  CreditCard,
  Download,
  Hand,
  KeyRound,
  Lock,
  MessageCircle,
  NotebookPen,
  Receipt,
  Smartphone,
  Target,
  Users,
  UsersRound,
} from "lucide-react";
import { categories } from "@business-os/verticals";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { Container } from "@/components/layout/container";
import { Section } from "@/components/layout/section";
import { BranchesMock } from "@/components/marketing/mocks";
import { ModuleIcon } from "@/components/modules/module-icon";
import { VerticalIcon } from "@/components/vertical-icon";
import { industryTexts } from "@/lib/verticals";

export const FEATURES = [
  { key: "schedule", Icon: CalendarDays },
  { key: "clients", Icon: Users },
  { key: "plans", Icon: CreditCard },
  { key: "app", Icon: Smartphone },
  { key: "ai", Icon: Bot },
  { key: "reports", Icon: BarChart3 },
  { key: "team", Icon: UsersRound },
  { key: "payments", Icon: Receipt },
  { key: "appointments", Icon: CalendarClock },
  { key: "crm", Icon: Target },
  { key: "messages", Icon: MessageCircle },
  { key: "records", Icon: NotebookPen },
] as const;

/** A section heading: optional eyebrow, title and subtitle, centered. `level` 1 when it is the
 * page's own heading. */
export function SectionHeading({ eyebrow, title, subtitle, id, level = 2 }: { eyebrow?: string; title: string; subtitle?: string; id?: string; level?: 1 | 2 }) {
  const Heading = level === 1 ? "h1" : "h2";
  return (
    <div className="mx-auto flex max-w-3xl flex-col items-center gap-3 text-center">
      {eyebrow && <p className="rounded-full bg-primary/10 px-3 py-1 text-sm font-semibold text-brand-ink">{eyebrow}</p>}
      <Heading id={id} className={level === 1 ? "text-4xl font-extrabold tracking-tight sm:text-5xl" : "text-3xl font-extrabold tracking-tight sm:text-5xl"}>
        {title}
      </Heading>
      {subtitle && <p className="text-lg text-muted">{subtitle}</p>}
    </div>
  );
}

/** Every core feature. On the features page, whose own heading already says it, the grid
 * gets the shorter "all in one place" heading. */
export async function FeatureGrid({ inFeaturesPage = false }: { inFeaturesPage?: boolean }) {
  const t = await getTranslations("marketing.features");
  return (
    <Section aria-labelledby="features-heading" innerClassName="flex flex-col gap-10">
      <SectionHeading
        id="features-heading"
        title={inFeaturesPage ? t("gridTitle") : t("title")}
        subtitle={inFeaturesPage ? t("gridSubtitle") : t("subtitle")}
      />
      <ul className="enter-items swipe gap-4 sm:grid sm:grid-cols-2 lg:grid-cols-4 2xl:grid-cols-6">
        {FEATURES.map(({ key, Icon }) => (
          <li key={key} className="card card-hover flex flex-col gap-3 p-6">
            <span className="icon-tile size-11">
              <Icon aria-hidden="true" className="size-5" />
            </span>
            <h3 className="font-semibold">{t(`items.${key}.title`)}</h3>
            <p className="text-sm text-muted">{t(`items.${key}.text`)}</p>
          </li>
        ))}
      </ul>
    </Section>
  );
}

export async function IndustryCards() {
  const t = await getTranslations("marketing.industries");
  const { text, points } = industryTexts(await getTranslations());
  const open = categories().filter((c) => c.status !== "planned");
  const soon = categories().filter((c) => c.status === "planned");
  return (
    <Section aria-labelledby="industries-heading" innerClassName="flex flex-col gap-10">
      <SectionHeading id="industries-heading" title={t("title")} subtitle={t("subtitle")} />
      <ul className="swipe gap-4 sm:grid sm:grid-cols-2 lg:grid-cols-3">
        {open.map(({ key, icon, color }) => (
          <li key={key}>
            <Link href={`/industries/${key}`} className="card card-hover group flex h-full flex-col gap-4 p-6">
              <span aria-hidden="true" className={`flex size-12 items-center justify-center rounded-2xl bg-gradient-to-br ${color} text-white shadow-lg`}>
                <VerticalIcon icon={icon} className="size-6" />
              </span>
              <span className="flex flex-col gap-1">
                <span className="text-lg font-semibold">{text(key, "name")}</span>
                <span className="text-sm text-muted">{text(key, "tagline")}</span>
              </span>
              <ul className="flex flex-col gap-1.5 text-sm">
                {points(key).map((point) => (
                  <li key={point} className="flex items-start gap-2">
                    <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-success" />
                    {point}
                  </li>
                ))}
              </ul>
              <span className="mt-auto inline-flex items-center gap-1 text-sm font-semibold text-primary">
                {t("more")}
                <ArrowLeft aria-hidden="true" className="size-4 transition-transform group-hover:-translate-x-1 ltr:rotate-180 ltr:group-hover:translate-x-1" />
              </span>
            </Link>
          </li>
        ))}
        {soon.length > 0 && (
          <li>
            <Link href="/industries" className="card card-hover group flex h-full flex-col gap-4 p-6">
              <span className="flex flex-col gap-1">
                <span className="text-lg font-semibold">{t("soonTitle")}</span>
                <span className="text-sm text-muted">{t("soonText")}</span>
              </span>
              <ul className="flex flex-wrap gap-2 text-sm">
                {soon.map(({ key, icon }) => (
                  <li key={key} className="flex items-center gap-1.5 rounded-full bg-background px-3 py-1 ring-1 ring-border">
                    <VerticalIcon icon={icon} className="size-3.5 text-muted" />
                    {text(key, "name")}
                  </li>
                ))}
              </ul>
              <span className="mt-auto inline-flex items-center gap-1 text-sm font-semibold text-primary">
                {t("all")}
                <ArrowLeft aria-hidden="true" className="size-4 transition-transform group-hover:-translate-x-1 ltr:rotate-180 ltr:group-hover:translate-x-1" />
              </span>
            </Link>
          </li>
        )}
      </ul>
    </Section>
  );
}

export async function Faq() {
  const t = await getTranslations("marketing.faq");
  const items = t.raw("items") as { q: string; a: string }[];
  return (
    <Section aria-labelledby="faq-heading" innerClassName="flex flex-col gap-8">
      <SectionHeading id="faq-heading" title={t("title")} />
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-3">
        {items.map((item) => (
          <details key={item.q} className="card group p-5 open:shadow-md">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-semibold">
              {item.q}
              <span aria-hidden="true" className="text-xl text-primary transition-transform group-open:rotate-45">
                +
              </span>
            </summary>
            <p className="mt-3 text-muted">{item.a}</p>
          </details>
        ))}
      </div>
    </Section>
  );
}

export async function CtaBand() {
  const t = await getTranslations("marketing.cta");
  return (
    <Section tone="inverse" spacing="loose" className="relative isolate overflow-hidden" innerClassName="flex flex-col items-center gap-5 text-center">
        <div aria-hidden="true" className="mk-grid pointer-events-none absolute inset-0 -z-10" />
        <div aria-hidden="true" className="pointer-events-none absolute -top-24 start-[15%] -z-10 size-72 rounded-full bg-primary/50 blur-[90px]" />
        <div aria-hidden="true" className="pointer-events-none absolute -bottom-24 end-[15%] -z-10 size-72 rounded-full bg-electric/30 blur-[90px]" />
        <h2 className="text-3xl font-extrabold tracking-tight sm:text-5xl">{t("title")}</h2>
        <p className="max-w-xl text-lg text-white/75">{t("text")}</p>
        <div className="flex flex-wrap justify-center gap-3">
          <Link href="/start" className="btn-primary btn-lg rounded-full px-7">
            {t("button")}
          </Link>
          <Link href="/contact" className="btn-lg inline-flex items-center justify-center rounded-full border border-white/25 px-7 font-semibold text-white transition-colors hover:bg-white/10">
            {t("contact")}
          </Link>
        </div>
    </Section>
  );
}

/** One owner, several businesses, each with branches (decision T76). */
export async function BranchesSection() {
  const t = await getTranslations("marketing.branches");
  return (
    <Section tone="surface" aria-labelledby="branches-heading" innerClassName="grid items-center gap-12 lg:grid-cols-2 lg:gap-20">
      <>
        <div className="flex flex-col gap-5">
          <p className="text-sm font-semibold text-primary">{t("eyebrow")}</p>
          <h2 id="branches-heading" className="text-3xl font-bold tracking-tight sm:text-4xl">
            {t("title")}
          </h2>
          <p className="text-lg text-muted">{t("text")}</p>
          <ul className="flex flex-col gap-2">
            {(t.raw("points") as string[]).map((point) => (
              <li key={point} className="flex items-start gap-2 font-medium">
                <Check aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-success" />
                {point}
              </li>
            ))}
          </ul>
        </div>
        <BranchesMock />
      </>
    </Section>
  );
}

const ADD_ONS = ["client_app", "ai_basic", "crm", "whatsapp", "extra_location"] as const;

/** The add-ons in one row, with a link to their prices. */
export async function AddOnsStrip() {
  const t = await getTranslations("marketing.addOns");
  const tModules = await getTranslations("modules");
  return (
    <Section aria-labelledby="add-ons-heading" spacing="compact" innerClassName="flex flex-col gap-8">
      <SectionHeading id="add-ons-heading" title={t("title")} subtitle={t("subtitle")} />
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {ADD_ONS.map((key) => (
          <li key={key} className="card card-hover flex flex-col items-center gap-3 p-5 text-center">
            <ModuleIcon module={key} size="lg" />
            <span className="font-semibold">{tModules(`names.${key}`)}</span>
          </li>
        ))}
      </ul>
      <Link href="/pricing" className="group mx-auto inline-flex items-center gap-1 font-semibold text-primary">
        {t("cta")}
        <ArrowLeft aria-hidden="true" className="size-4 transition-transform group-hover:-translate-x-1 ltr:rotate-180 ltr:group-hover:translate-x-1" />
      </Link>
    </Section>
  );
}

const SAFETY = [
  { key: "separate", Icon: Lock },
  { key: "approve", Icon: Hand },
  { key: "roles", Icon: KeyRound },
  { key: "yours", Icon: Download },
] as const;

/** How MyBiz keeps a business's data and actions safe. */
export async function SafetySection() {
  const t = await getTranslations("marketing.safety");
  return (
    <Section aria-labelledby="safety-heading" innerClassName="flex flex-col gap-10">
      <SectionHeading id="safety-heading" eyebrow={t("eyebrow")} title={t("title")} subtitle={t("subtitle")} />
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {SAFETY.map(({ key, Icon }) => (
          <li key={key} className="card flex flex-col gap-3 p-6">
            <span aria-hidden="true" className="flex size-11 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 text-white shadow-sm">
              <Icon className="size-5" />
            </span>
            <h3 className="font-semibold">{t(`items.${key}.title`)}</h3>
            <p className="text-sm text-muted">{t(`items.${key}.text`)}</p>
          </li>
        ))}
      </ul>
    </Section>
  );
}

/** The dark band that opens a marketing subpage: eyebrow, the page's own h1, a subtitle and
 * optional extra content (a switcher, a button), on the same navy glow as the home hero. */
export function PageHero({ eyebrow, title, subtitle, children }: { eyebrow?: string; title: string; subtitle?: string; children?: React.ReactNode }) {
  return (
    <section className="relative isolate overflow-hidden bg-navy text-white">
      <div aria-hidden="true" className="mk-grid pointer-events-none absolute inset-0 -z-10" />
      <div aria-hidden="true" className="pointer-events-none absolute -top-40 start-[15%] -z-10 size-[28rem] rounded-full bg-primary/35 blur-[120px]" />
      <div aria-hidden="true" className="pointer-events-none absolute -bottom-48 end-[10%] -z-10 size-[24rem] rounded-full bg-electric/20 blur-[120px]" />
      <Container className="flex flex-col items-center gap-4 py-16 text-center sm:py-20 lg:py-24">
        {eyebrow && <p className="rounded-full border border-white/15 bg-white/5 px-4 py-1.5 text-sm font-medium text-white/85">{eyebrow}</p>}
        <h1 className="text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">{title}</h1>
        {subtitle && <p className="max-w-3xl text-lg leading-relaxed text-white/75 sm:text-xl">{subtitle}</p>}
        {children}
    </Container>
    </section>
  );
}
