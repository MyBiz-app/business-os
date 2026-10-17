import { getLocale, getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { signOutToLogin } from "@/app/(auth)/actions";
import { getApi } from "@/lib/api";
import { getActiveMembership } from "@/lib/tenant";

import { reopenBusiness } from "./actions";
import { Container } from "@/components/layout/container";

/** Where people land in a business that was closed: its owner can reopen it for 90 days, anyone
 * else is told to ask the owner. Does not use getTenant (which sends closed businesses here). */
export default async function ClosedPage() {
  const { membership } = await getActiveMembership();
  if (!membership) redirect("/welcome");
  const t = await getTranslations("closure");
  const locale = await getLocale();
  const owner = membership.role === "owner";
  const { data: closure } = owner
    ? await (await getApi()).GET("/tenants/current/closure", { params: { header: { "X-Tenant-Id": membership.tenant_id } } })
    : { data: undefined };
  if (owner && !closure?.closed_at) redirect("/dashboard");
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "long" });

  return (
    <Container as="main" size="prose" className="enter flex max-w-xl flex-1 flex-col justify-center gap-6 py-12">
      <section aria-labelledby="closed-heading" className="flex flex-col gap-4 card p-6">
        <h1 id="closed-heading" className="text-2xl font-bold">
          {t("closedTitle")}
        </h1>
        {owner && closure?.closed_at && closure.delete_after ? (
          <>
            <p className="text-sm text-muted">{t("closedOn", { date: when.format(new Date(closure.closed_at)) })}</p>
            <p className="text-sm">{t("deleteOn", { date: when.format(new Date(closure.delete_after)) })}</p>
            <form action={reopenBusiness}>
              <button type="submit" className="btn-primary px-4 py-2.5 text-sm">
                {t("reopen")}
              </button>
            </form>
          </>
        ) : (
          <p className="text-sm text-muted">{t("notOwner", { name: membership.tenant_name })}</p>
        )}
      </section>
      <form action={signOutToLogin} className="text-center">
        <button type="submit" className="btn-link text-sm text-primary-ink underline">
          {t("signOut")}
        </button>
      </form>
    </Container>
  );
}
