import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { TopicHeader } from "../../topic-header";
import { CancelFlow } from "./cancel-flow";

/** Cancelling the MyBiz subscription: why, an offer to pay less, and a confirmation (R33). */
export default async function CancelSubscriptionPage() {
  const t = await getTranslations("billing");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenant();
  if (!canManageSettings(tenant) || tenant.role !== "owner") redirect("/settings/billing");
  const billing = unwrap(await api.GET("/billing", { params: scope }));
  if (billing.collection.cancel_at) redirect("/settings/billing");
  const options = unwrap(await api.GET("/billing/cancel", { params: scope }));
  const money = (amount: number) => formatMoney(amount, options.currency, locale);

  return (
    <div className="flex max-w-[44rem] flex-col gap-6">
      <Link href="/settings/billing" className="text-sm text-primary-ink underline-offset-4 hover:underline">
        {t("back")}
      </Link>
      <TopicHeader title={t("cancelFlow.title")} description={t("cancelFlow.intro")} />
      <CancelFlow
        endsOn={formatDay(options.ends_at, locale, { day: "numeric", month: "long", year: "numeric" })}
        refund={options.refund_minor ? money(options.refund_minor) : null}
        pause={{ available: options.pause_available, fee: money(options.pause_fee_minor), maxMonths: options.pause_max_months }}
      />
      <p className="text-sm text-muted">
        <Link href="/legal/cancellation" target="_blank" className="text-primary-ink underline underline-offset-4">
          {t("subscription.policy")}
        </Link>
      </p>
    </div>
  );
}
