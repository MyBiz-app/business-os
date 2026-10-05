import {
  ArrowLeft,
  BarChart3,
  Bot,
  CalendarDays,
  Car,
  Check,
  CalendarClock,
  CreditCard,
  Dumbbell,
  MessageCircle,
  NotebookPen,
  Receipt,
  Scissors,
  Smartphone,
  Stethoscope,
  Target,
  Users,
  UsersRound,
} from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

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

export const INDUSTRIES = [
  { key: "fitness", Icon: Dumbbell, color: "from-indigo-500 to-violet-500" },
  { key: "beauty", Icon: Scissors, color: "from-pink-500 to-rose-500" },
  { key: "clinic", Icon: Stethoscope, color: "from-teal-500 to-emerald-500" },
  { key: "garage", Icon: Car, color: "from-amber-500 to-orange-500" },
] as const;

export type IndustryKey = (typeof INDUSTRIES)[number]["key"];

/** A section heading: optional eyebrow, title and subtitle, centered. */
export function SectionHeading({ eyebrow, title, subtitle, id }: { eyebrow?: string; title: string; subtitle?: string; id?: string }) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-3 text-center">
      {eyebrow && <p className="text-sm font-semibold text-primary">{eyebrow}</p>}
      <h2 id={id} className="text-3xl font-bold tracking-tight sm:text-4xl">
        {title}
      </h2>
      {subtitle && <p className="text-lg text-muted">{subtitle}</p>}
    </div>
  );
}

export async function FeatureGrid() {
  const t = await getTranslations("marketing.features");
  return (
    <section aria-labelledby="features-heading" className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-6 py-20">
      <SectionHeading id="features-heading" title={t("title")} subtitle={t("subtitle")} />
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
  return (
    <section aria-labelledby="industries-heading" className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-6 py-20">
      <SectionHeading id="industries-heading" title={t("title")} subtitle={t("subtitle")} />
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {INDUSTRIES.map(({ key, Icon, color }) => (
          <li key={key}>
            <Link href={`/industries/${key}`} className="card card-hover group flex h-full flex-col gap-4 p-6">
              <span aria-hidden="true" className={`flex size-12 items-center justify-center rounded-2xl bg-gradient-to-br ${color} text-white shadow-lg`}>
                <Icon className="size-6" />
              </span>
              <span className="flex flex-col gap-1">
                <span className="text-lg font-semibold">{t(`items.${key}.name`)}</span>
                <span className="text-sm text-muted">{t(`items.${key}.tagline`)}</span>
              </span>
              <ul className="flex flex-col gap-1.5 text-sm">
                {(t.raw(`items.${key}.points`) as string[]).map((point) => (
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
