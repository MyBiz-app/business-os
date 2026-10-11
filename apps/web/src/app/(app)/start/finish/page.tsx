import type { components } from "@business-os/api-client";
import { Check, Lock } from "lucide-react";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { API_URL } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { decodePlan, encodePlan, priceLines, trialEndsOn } from "@/lib/signup-plan";
import { industryTexts } from "@/lib/verticals";

import { FinishForm } from "./finish-form";
import { isolate } from "@/lib/bidi";

type Catalog = components["schemas"]["Catalog"];

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("start.finish");
  return { title: `${t("title")} · ${BRAND.name}` };
}

async function loadCatalog(currency: string): Promise<Catalog | null> {
  try {
    const response = await fetch(`${API_URL}/public/pricing?currency=${currency}`, { next: { revalidate: 3600 } });
    return response.ok ? ((await response.json()) as Catalog) : null;
  } catch {
    return null;
  }
}

/** The payment step of the sign-up journey, after the account exists. */
export default async function FinishPage({ searchParams }: PageProps<"/start/finish">) {
  const t = await getTranslations("start");
  const tModules = await getTranslations("modules");
  const { text } = industryTexts(await getTranslations());
  const locale = await getLocale();
  const plan = decodePlan((await searchParams).p);
  const catalog = plan ? await loadCatalog(plan.currency) : null;

  if (!plan || !catalog) {
    return (
      <main className="enter mx-auto flex max-w-xl flex-col items-center gap-4 px-6 py-24 text-center">
        <h1 className="text-2xl font-bold">{t("finish.title")}</h1>
        <p className="text-muted">{t(plan ? "finish.errors.generic" : "finish.invalid")}</p>
        <Link href="/start" className="btn-primary px-5 py-3">
          {t("finish.rebuild")}
        </Link>
        <Link href="/welcome?fresh=1" className="text-sm font-semibold text-primary underline-offset-4 hover:underline">
          {t("finish.later")}
        </Link>
      </main>
    );
  }

  const money = (amount: number) => formatMoney(amount, plan.currency, locale);
  const { lines, total } = priceLines(catalog, plan);
  const trialEnds = new Date(`${trialEndsOn()}T12:00:00`).toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric" });

  return (
    <main className="mx-auto grid w-full max-w-5xl gap-8 px-4 py-10 sm:px-6 lg:grid-cols-[1fr_20rem]">
      <section aria-labelledby="finish-heading" className="enter flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <h1 id="finish-heading" className="text-3xl font-extrabold tracking-tight">
            {t("finish.title")}
          </h1>
          <p className="text-lg text-muted">{t("finish.subtitle")}</p>
        </div>
        <FinishForm plan={encodePlan(plan)} />
        <p className="flex items-center gap-2 text-sm text-muted">
          <Lock aria-hidden="true" className="size-4" />
          {t("finish.secure")}
        </p>
        <Link href="/welcome?fresh=1" className="w-fit text-sm text-muted underline underline-offset-4 hover:text-foreground">
          {t("finish.later")}
        </Link>
      </section>

      <aside aria-labelledby="finish-plan" className="card flex h-fit flex-col gap-4 p-5 lg:sticky lg:top-24">
        <h2 id="finish-plan" className="font-bold">
          {t("summary.business", { name: isolate(plan.name), vertical: text(plan.vertical, "name") })}
        </h2>
        <ul className="flex flex-col gap-2">
          {lines.map((line) => (
            <li key={line.key} className="flex items-center justify-between gap-3 text-sm">
              <span className="flex items-center gap-1.5">
                <Check aria-hidden="true" className="size-4 shrink-0 text-success" />
                {line.key === "core" ? tModules("core") : tModules(`names.${line.key}`)}
                {line.quantity > 1 && <span className="text-muted" dir="ltr">× {line.quantity}</span>}
              </span>
              <bdi className="font-semibold">{money(line.amount)}</bdi>
            </li>
          ))}
        </ul>
        <div className="flex flex-col gap-1 border-t border-border pt-3">
          <p className="flex items-baseline justify-between gap-2">
            <span className="text-sm font-semibold">{t("summary.monthly")}</span>
            <span className="text-xl font-extrabold">
              <bdi>{money(total)}</bdi>
            </span>
          </p>
          <p className="flex items-baseline justify-between gap-2 text-success">
            <span className="text-sm font-semibold">{t("summary.today")}</span>
            <span className="font-bold">
              <bdi>{money(0)}</bdi>
            </span>
          </p>
        </div>
        <p className="text-sm text-muted">{t("summary.trialEnds", { date: trialEnds })}</p>
        <Link href="/start" className="text-sm font-semibold text-primary underline-offset-4 hover:underline">
          {t("summary.edit")}
        </Link>
      </aside>
    </main>
  );
}
