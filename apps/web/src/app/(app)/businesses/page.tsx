import { vertical } from "@business-os/verticals";
import { ArrowLeft, CalendarDays, MapPin, Plus, Users, Wallet } from "lucide-react";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Image from "next/image";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { VerticalIcon } from "@/components/vertical-icon";
import { apiAssetUrl, getApi, unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { getActiveMembership } from "@/lib/tenant";
import { industryTexts } from "@/lib/verticals";

import { switchBusiness } from "../(tenant)/_menu/actions";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("businesses");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** Every business the person belongs to, side by side: its industry, branches and the numbers of
 * today and this month, one click from opening it. */
export default async function BusinessesPage() {
  const t = await getTranslations("businesses");
  const tAll = await getTranslations();
  const { text } = industryTexts(tAll);
  const locale = await getLocale();
  const { membership } = await getActiveMembership();
  const businesses = unwrap(await (await getApi()).GET("/me/businesses"));
  const number = new Intl.NumberFormat(locale);
  const branchCount = businesses.reduce((sum, b) => sum + b.branches.length, 0);

  return (
    <main className="enter mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-6 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold">{t("title")}</h1>
          <p className="text-muted">{t("summary", { businesses: businesses.length, branches: branchCount })}</p>
        </div>
        <Link href="/onboarding" className="btn-primary gap-2 px-4 py-2">
          <Plus aria-hidden="true" className="size-4" />
          {t("add")}
        </Link>
      </div>

      <ul className="enter-items grid gap-5 md:grid-cols-2">
        {businesses.map((business) => {
          const industry = vertical(business.vertical);
          const logo = apiAssetUrl(business.logo_url);
          const current = business.tenant_id === membership?.tenant_id;
          const shown = business.branches.slice(0, 4);
          return (
            <li key={business.tenant_id}>
              <article
                className={`card card-hover relative flex h-full flex-col overflow-hidden ${current ? "ring-2 ring-primary" : ""}`}
                style={business.primary_color ? { borderTop: `4px solid ${business.primary_color}` } : undefined}
              >
                <div className="flex items-start gap-4 p-6 pb-4">
                  {logo ? (
                    <Image src={logo} alt="" width={48} height={48} unoptimized className="size-12 rounded-2xl object-contain shadow-sm" />
                  ) : (
                    <span
                      aria-hidden="true"
                      className={`flex size-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br text-white shadow-md ${industry?.color ?? "from-slate-500 to-slate-700"}`}
                    >
                      {industry ? <VerticalIcon icon={industry.icon} className="size-6" /> : business.name.slice(0, 1)}
                    </span>
                  )}
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <h2 dir="auto" className="truncate text-xl font-bold">
                      {business.name}
                    </h2>
                    <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
                      {industry && <span>{text(business.vertical, "name")}</span>}
                      <span className="rounded-full bg-background px-2 py-0.5 text-xs font-medium ring-1 ring-border">
                        {tAll(`roles.${business.role}`)}
                      </span>
                      {current && <span className="text-xs font-semibold text-primary">{t("open")}</span>}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 px-6 pb-4 text-sm">
                  <MapPin aria-hidden="true" className="size-4 text-muted" />
                  <span className="font-medium">{t("branches", { count: business.branches.length })}</span>
                  {shown.map((branch) => (
                    <span key={branch} dir="auto" className="rounded-full bg-background px-2.5 py-0.5 text-xs ring-1 ring-border">
                      {branch}
                    </span>
                  ))}
                  {business.branches.length > shown.length && (
                    <span className="text-xs text-muted">{t("more", { count: business.branches.length - shown.length })}</span>
                  )}
                </div>

                <dl className="mt-auto grid grid-cols-3 border-t border-border">
                  <Stat icon={<CalendarDays className="size-4" />} label={t("today")} value={number.format(business.sessions_today)} />
                  <Stat
                    icon={<Users className="size-4" />}
                    label={t("activeClients")}
                    value={business.active_clients === null ? "—" : number.format(business.active_clients)}
                  />
                  <Stat
                    icon={<Wallet className="size-4" />}
                    label={t("revenue")}
                    value={business.revenue_month === null ? "—" : formatMoney(business.revenue_month, business.currency, locale)}
                  />
                </dl>

                <form action={switchBusiness} className="border-t border-border">
                  <input type="hidden" name="tenant_id" value={business.tenant_id} />
                  <button type="submit" className="group flex w-full items-center justify-between px-6 py-3 text-sm font-semibold text-primary hover:bg-background/60">
                    {t("enter", { name: business.name })}
                    <ArrowLeft aria-hidden="true" className="size-4 transition-transform group-hover:-translate-x-1 ltr:rotate-180 ltr:group-hover:translate-x-1" />
                  </button>
                </form>
              </article>
            </li>
          );
        })}
        <li>
          <Link
            href="/onboarding"
            className="flex h-full min-h-56 flex-col items-center justify-center gap-3 rounded-3xl border-2 border-dashed border-border p-6 text-center text-muted transition-colors hover:border-primary hover:text-primary"
          >
            <Plus aria-hidden="true" className="size-8" />
            <span className="font-semibold">{t("add")}</span>
            <span className="max-w-xs text-sm">{t("addHint")}</span>
          </Link>
        </li>
      </ul>
    </main>
  );
}

function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 px-4 py-4 [&:not(:first-child)]:border-s [&:not(:first-child)]:border-border">
      <dt className="flex items-center gap-1.5 text-xs text-muted">
        <span aria-hidden="true">{icon}</span>
        {label}
      </dt>
      <dd className="text-lg font-bold tabular-nums">{value}</dd>
    </div>
  );
}
