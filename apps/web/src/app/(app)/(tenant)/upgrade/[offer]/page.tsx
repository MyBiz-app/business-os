import { Check, Lock, Plus, Sparkles } from "lucide-react";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { SubmitButton } from "@/components/form/submit-button";
import { ChatMock, PhoneMock } from "@/components/marketing/mocks";
import { OfferPicture } from "@/components/modules/offer-picture";
import { unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";
import { hasUpgrade, isUpgrade, UPGRADES } from "@/lib/upgrades";

import { addToPlan } from "./actions";

export async function generateMetadata({ params }: PageProps<"/upgrade/[offer]">): Promise<Metadata> {
  const { offer } = await params;
  if (!isUpgrade(offer)) return {};
  const t = await getTranslations("start.offers");
  return { title: `${t(`${offer}.eyebrow`)} · MyBiz` };
}

/** A module the business doesn't have: what it does, a peek, and what adding it changes on the
 * invoice. Whoever manages settings can add it in one click. */
export default async function UpgradePage({ params }: PageProps<"/upgrade/[offer]">) {
  const { offer } = await params;
  if (!isUpgrade(offer)) notFound();
  const t = await getTranslations("upgrade");
  const tOffers = await getTranslations("start.offers");
  const tModules = await getTranslations("modules");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenant();
  if (hasUpgrade(tenant.modules, offer)) redirect(UPGRADES[offer].href);

  const manager = canManageSettings(tenant);
  const [catalog, current, billing] = await Promise.all([
    api.GET("/modules/catalog", { params: { query: { currency: tenant.currency } } }).then(unwrap),
    api.GET("/tenants/current/modules", { params: scope }).then(unwrap),
    manager ? api.GET("/billing", { params: scope }).then((r) => r.data) : Promise.resolve(undefined),
  ]);
  const money = (amount: number) => formatMoney(amount, tenant.currency, locale);
  const priceOf = (key: string) => catalog.modules.find((m) => m.key === key)?.price ?? 0;
  const keys = UPGRADES[offer].modules;
  const firstKey = keys[0];
  const trialEnds = billing?.in_trial
    ? new Date(billing.trial_ends_at).toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric", timeZone: tenant.time_zone })
    : null;
  const points = offer === "ai" ? null : (tOffers.raw(`${offer}.points`) as string[]);
  const picture =
    offer === "client_app" ? (
      <PhoneMock />
    ) : offer === "ai" ? (
      <ChatMock question={tOffers("ai.question")} answer={tOffers("ai.answer")} />
    ) : (
      <OfferPicture offer={offer} />
    );

  const addButton = (key: string) => (
    <form action={addToPlan.bind(null, offer, key)}>
      <SubmitButton>
        <Plus aria-hidden="true" className="size-4" />
        {t("add", { price: money(priceOf(key)) })}
      </SubmitButton>
    </form>
  );

  return (
    <main className="enter mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-6 py-10">
      <div className="flex flex-col items-start gap-3">
        <p className="flex items-center gap-1.5 rounded-full bg-foreground/5 px-3 py-1 text-sm font-semibold text-muted">
          <Lock aria-hidden="true" className="size-3.5" />
          {t("notInPlan")}
        </p>
        <p className="text-sm font-semibold text-primary">{tOffers(`${offer}.eyebrow`)}</p>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">{tOffers(`${offer}.title`)}</h1>
        <p className="max-w-2xl text-lg text-muted">{tOffers(`${offer}.text`)}</p>
      </div>

      <div className="grid items-start gap-8 lg:grid-cols-2">
        <div className="flex flex-col gap-6">
          {points && (
            <ul className="flex flex-col gap-2">
              {points.map((point) => (
                <li key={point} className="flex items-start gap-2 font-medium">
                  <Check aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-success" />
                  {point}
                </li>
              ))}
            </ul>
          )}

          {offer === "ai" ? (
            <section aria-labelledby="tiers" className="flex flex-col gap-3">
              <h2 id="tiers" className="font-semibold">
                {t("chooseTier")}
              </h2>
              <div className="grid gap-4 sm:grid-cols-2">
                {keys.map((key) => (
                  <div key={key} className="card flex flex-col gap-3 p-5">
                    <h3 className="text-lg font-bold">{tOffers(`ai.tiers.${key as "ai_basic"}.title`)}</h3>
                    <p className="flex-1 text-sm text-muted">{tOffers(`ai.tiers.${key as "ai_basic"}.text`)}</p>
                    <p className="text-xl font-extrabold">
                      + <bdi>{money(priceOf(key))}</bdi> <span className="text-sm font-normal text-muted">{t("perMonth")}</span>
                    </p>
                    {manager && addButton(key)}
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {manager ? (
            <section aria-labelledby="invoice" className="card flex flex-col gap-3 p-5">
              <h2 id="invoice" className="font-semibold">
                {t("invoiceTitle")}
              </h2>
              <dl className="flex flex-col gap-2 text-sm">
                <div className="flex items-baseline justify-between gap-3">
                  <dt className="text-muted">{t("now")}</dt>
                  <dd className="font-semibold">
                    <bdi>{money(current.quote.total)}</bdi> {t("perMonth")}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-3">
                  <dt className="text-muted">{t("with", { name: tModules(`names.${firstKey}`) })}</dt>
                  <dd className="text-lg font-extrabold">
                    <bdi>{money(current.quote.total + priceOf(firstKey))}</bdi> {t("perMonth")}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-3 border-t border-border pt-2">
                  <dt className="text-muted">{t("difference")}</dt>
                  <dd className="font-semibold text-primary">
                    + <bdi>{money(priceOf(firstKey))}</bdi>
                  </dd>
                </div>
              </dl>
              <p className="text-sm text-muted">{trialEnds ? t("inTrial", { date: trialEnds }) : t("afterTrial")}</p>
              {offer !== "ai" && addButton(firstKey)}
              <Link href="/settings/modules" className="text-sm font-semibold text-primary underline-offset-4 hover:underline">
                {t("manage")}
              </Link>
            </section>
          ) : (
            <p role="note" className="card p-5 text-sm">
              {t("noPermission")}
            </p>
          )}
        </div>

        <figure className="relative">
          <figcaption className="mb-3 flex items-center gap-1.5 text-sm font-semibold text-muted">
            <Sparkles aria-hidden="true" className="size-4 text-primary" />
            {t("peek")}
          </figcaption>
          <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-500/10 to-fuchsia-500/10 p-6">
            {picture}
            <span aria-hidden="true" className="absolute end-4 top-4 flex size-9 items-center justify-center rounded-full bg-surface shadow">
              <Lock className="size-4 text-muted" />
            </span>
          </div>
        </figure>
      </div>
    </main>
  );
}
