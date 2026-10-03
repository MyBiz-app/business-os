import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { getApi, unwrap } from "@/lib/api";
import { getActiveMembership } from "@/lib/tenant";

import { BusinessSwitcher } from "./business-switcher";

export default async function DashboardPage() {
  const t = await getTranslations();
  const { me, membership } = await getActiveMembership();
  if (!membership) redirect("/onboarding");

  const api = await getApi();
  const tenant = unwrap(
    await api.GET("/tenants/current", {
      params: { header: { "X-Tenant-Id": membership.tenant_id } },
    }),
  );

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-8 px-6 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold">{t("dashboard.welcome", { name: tenant.name })}</h1>
          <p className="text-muted">
            {t("dashboard.yourRole", { role: t(`roles.${tenant.role}`) })} · <span dir="ltr">{me.email}</span>
          </p>
        </div>
        <BusinessSwitcher current={tenant.id} memberships={me.memberships} />
      </div>

      <section aria-labelledby="today-heading" className="rounded-2xl border border-border bg-surface p-6">
        <h2 id="today-heading" className="mb-2 text-lg font-semibold">
          {t("dashboard.today")}
        </h2>
        <p className="text-muted">{t("dashboard.emptyToday")}</p>
      </section>
    </main>
  );
}
