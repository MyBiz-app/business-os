import type { components } from "@business-os/api-client";
import { ArrowRight, BookOpen, Check, CreditCard, Palette, CalendarDays, Sparkles, Tags, Users, UsersRound } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { isolate } from "@/lib/bidi";

type GettingStarted = components["schemas"]["GettingStarted"];
export type SetupStep = GettingStarted["steps"][number]["key"];

export const SETUP_STEPS: Record<SetupStep, { href: string; Icon: typeof Palette }> = {
  branding: { href: "/settings", Icon: Palette },
  services: { href: "/services", Icon: Tags },
  schedule: { href: "/schedule", Icon: CalendarDays },
  team: { href: "/team", Icon: UsersRound },
  clients: { href: "/clients", Icon: Users },
  card: { href: "/settings/billing", Icon: CreditCard },
};

/** The first-steps checklist on the dashboard, until everything is done. Right after sign-up
 * (`welcome`) it opens with a welcome. */
export async function GettingStartedCard({ setup, welcome, business }: { setup: GettingStarted; welcome: boolean; business: string }) {
  const t = await getTranslations("gettingStarted");
  const percent = Math.round((setup.done / setup.total) * 100);

  return (
    <section aria-labelledby="setup-heading" className={`${welcome ? "card-accent" : "card"} flex flex-col gap-5 p-6`}>
      {welcome && (
        <div className="flex flex-col gap-2">
          <p className="flex items-center gap-2 text-sm font-semibold text-primary">
            <Sparkles aria-hidden="true" className="size-4" />
            {t("title")}
          </p>
          <h2 className="text-2xl font-extrabold tracking-tight">{t("welcomeTitle", { name: isolate(business) })}</h2>
          <p className="text-muted">{t("welcomeText")}</p>
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="setup-heading" className={welcome ? "sr-only" : "text-lg font-semibold"}>
          {t("title")}
        </h2>
        <p className="text-sm font-medium text-muted">{t("progress", { done: setup.done, total: setup.total })}</p>
        <Link href="/getting-started" className="flex items-center gap-1.5 text-sm font-semibold text-primary underline-offset-4 hover:underline">
          <BookOpen aria-hidden="true" className="size-4" />
          {t("guide")}
        </Link>
      </div>
      <div
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={t("progress", { done: setup.done, total: setup.total })}
        className="h-2 overflow-hidden rounded-full bg-foreground/10"
      >
        <span className="block h-full rounded-full bg-gradient-to-r from-brand-from to-brand-to transition-[width] duration-700" style={{ width: `${percent}%` }} />
      </div>
      <ol className="enter-items grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {setup.steps.map((step) => {
          const { href, Icon } = SETUP_STEPS[step.key];
          return (
            <li key={step.key}>
              <Link
                href={href}
                className={`group flex h-full items-start gap-3 rounded-xl border p-4 transition-colors ${
                  step.done ? "border-success/40 bg-success/5" : "border-border bg-surface hover:border-primary/50"
                }`}
              >
                <span
                  aria-hidden="true"
                  className={`flex size-9 shrink-0 items-center justify-center rounded-xl ${step.done ? "bg-success text-white dark:text-zinc-950" : "icon-tile"}`}
                >
                  {step.done ? <Check className="size-5" /> : <Icon className="size-5" />}
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className={`font-semibold ${step.done ? "text-muted line-through" : ""}`}>{t(`steps.${step.key}.title`)}</span>
                  <span className="text-sm text-muted">{t(`steps.${step.key}.text`)}</span>
                </span>
                {!step.done && <ArrowRight aria-hidden="true" className="mt-1 size-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5 rtl:rotate-180 rtl:group-hover:-translate-x-0.5" />}
              </Link>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
