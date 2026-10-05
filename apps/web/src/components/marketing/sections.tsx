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
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-3 text-center">
      {eyebrow && <p className="text-sm font-semibold text-primary">{eyebrow}</p>}
      <Heading id={id} className={level === 1 ? "text-4xl font-extrabold tracking-tight sm:text-5xl" : "text-3xl font-bold tracking-tight sm:text-4xl"}>
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
    <section aria-labelledby="features-heading" className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-6 py-20">
      <SectionHeading
        id="features-heading"
        title={inFeaturesPage ? t("gridTitle") : t("title")}
        subtitle={inFeaturesPage ? t("gridSubtitle") : t("subtitle")}
      />
      <ul className="enter-items grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
    </section>
  );
}

export async function IndustryCards() {
  const t = await getTranslations("marketing.industries");
  const { text, points } = industryTexts(await getTranslations());
  const open = categories().filter((c) => c.status !== "planned");
  const soon = categories().filter((c) => c.status === "planned");
  return (
    <section aria-labelledby="industries-heading" className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-6 py-20">
      <SectionHeading id="industries-heading" title={t("title")} subtitle={t("subtitle")} />
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
    </section>
  );
}

export async function Faq() {
  const t = await getTranslations("marketing.faq");
  const items = t.raw("items") as { q: string; a: string }[];
  return (
    <section aria-labelledby="faq-heading" className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-6 py-20">
      <SectionHeading id="faq-heading" title={t("title")} />
      <div className="flex flex-col gap-3">
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
    </section>
  );
}

export async function CtaBand() {
  const t = await getTranslations("marketing.cta");
  return (
    <section className="px-6 py-20">
      <div className="relative mx-auto flex max-w-5xl flex-col items-center gap-5 overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-600 via-violet-600 to-fuchsia-600 px-6 py-14 text-center text-white shadow-2xl">
        <div aria-hidden="true" className="pointer-events-none absolute -top-24 -end-24 size-72 rounded-full bg-white/15 blur-3xl" />
        <h2 className="relative text-3xl font-bold tracking-tight sm:text-4xl">{t("title")}</h2>
        <p className="relative max-w-xl text-lg text-white/85">{t("text")}</p>
        <div className="relative flex flex-wrap justify-center gap-3">
          <Link href="/start" className="rounded-xl bg-white px-6 py-3 text-lg font-semibold text-indigo-700 shadow-lg transition-transform hover:-translate-y-0.5">
            {t("button")}
          </Link>
          <Link href="/contact" className="rounded-xl border border-white/40 px-6 py-3 text-lg font-semibold text-white transition-colors hover:bg-white/10">
            {t("contact")}
          </Link>
        </div>
      </div>
    </section>
  );
}

/** One owner, several businesses, each with branches (decision T76). */
export async function BranchesSection() {
  const t = await getTranslations("marketing.branches");
  return (
    <section aria-labelledby="branches-heading" className="bg-surface/60 py-20">
      <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 lg:grid-cols-2">
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
      </div>
    </section>
  );
}

const ADD_ONS = ["client_app", "ai_basic", "crm", "whatsapp", "extra_location"] as const;

/** The add-ons in one row, with a link to their prices. */
export async function AddOnsStrip() {
  const t = await getTranslations("marketing.addOns");
  const tModules = await getTranslations("modules");
  return (
    <section aria-labelledby="add-ons-heading" className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-16">
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
    </section>
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
    <section aria-labelledby="safety-heading" className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-6 py-20">
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
    </section>
  );
}
