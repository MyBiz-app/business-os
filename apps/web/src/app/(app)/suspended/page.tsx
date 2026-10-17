import { getLocale, getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { signOutToLogin } from "@/app/(auth)/actions";
import { Container } from "@/components/layout/container";
import { getApi } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { getActiveMembership } from "@/lib/tenant";

import { resumeEndedSubscription, settleInvoices } from "./actions";

/** Where people land in a business that is suspended for an unpaid MyBiz invoice, or whose
 * subscription ended. Only the owner can settle it; everyone else is told to ask. Does not use
 * getTenant (which sends suspended businesses here), because the business's data is locked. */
export default async function SuspendedPage() {
  const { membership } = await getActiveMembership();
  if (!membership) redirect("/welcome");
  const t = await getTranslations("billing");
  const tClosure = await getTranslations("closure");
  const locale = await getLocale();
  const owner = membership.role === "owner";
  const { data: billing } = owner
    ? await (await getApi()).GET("/billing", { params: { header: { "X-Tenant-Id": membership.tenant_id } } })
    : { data: undefined };
  if (billing && billing.collection.state !== "suspended") redirect("/dashboard");
  const owes = billing ? billing.balance_due > 0 : false;

  return (
    <Container as="main" size="prose" className="enter flex max-w-xl flex-1 flex-col justify-center gap-6 py-12">
      <section aria-labelledby="suspended-heading" className="flex flex-col gap-4 card p-6">
        <h1 id="suspended-heading" className="text-2xl font-bold">
          {t("suspended.title")}
        </h1>
        {billing ? (
          <>
            <p className="text-sm text-muted">{owes ? t("suspended.unpaid") : t("suspended.ended")}</p>
            {owes ? (
              <>
                <p className="text-sm font-medium">
                  {t("suspended.owed", { amount: formatMoney(billing.balance_due, billing.estimate.currency, locale) })}
                </p>
                <form action={settleInvoices}>
                  <button type="submit" className="btn-primary px-4 py-2.5 text-sm">
                    {billing.payment_method ? t("payNow") : t("suspended.addCard")}
                  </button>
                </form>
              </>
            ) : (
              <form action={resumeEndedSubscription}>
                <button type="submit" className="btn-primary px-4 py-2.5 text-sm">
                  {t("suspended.resume")}
                </button>
              </form>
            )}
          </>
        ) : (
          <p className="text-sm text-muted">{t("suspended.notOwner", { name: membership.tenant_name })}</p>
        )}
      </section>
      <form action={signOutToLogin} className="text-center">
        <button type="submit" className="btn-link text-sm text-primary-ink underline">
          {tClosure("signOut")}
        </button>
      </form>
    </Container>
  );
}
