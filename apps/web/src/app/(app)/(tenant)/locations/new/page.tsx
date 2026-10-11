import { getLocale, getTranslations } from "next-intl/server";

import { BackLink } from "@/components/back-link";
import { unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { canManageTeam } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { addBranch } from "../actions";
import { NewBranchForm } from "./new-branch-form";

export default async function NewLocationPage() {
  const t = await getTranslations();
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("business.settings");
  const [preview, locations, team] = await Promise.all([
    api.GET("/locations/new-branch", { params: scope }).then(unwrap),
    api.GET("/locations", { params: scope }).then(unwrap),
    canManageTeam(tenant) ? api.GET("/staff", { params: scope }).then(unwrap) : Promise.resolve(null),
  ]);

  const money = (amount: number) => formatMoney(amount, preview.currency, locale);
  // Members with no branches already work everywhere, so only the narrowed ones are offered.
  const people = (team?.members ?? [])
    .filter((m) => m.location_ids.length > 0)
    .map((m) => ({ id: m.user_id, name: m.full_name ?? m.email }));

  return (
    <main className="enter mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <BackLink href="/locations" label={t("nav.locations")} />
      <h1 className="text-3xl font-bold">{t("locations.addBranch.title")}</h1>
      {preview.chargeable && (
        <section aria-labelledby="charge-heading" className="card flex flex-col gap-2 border-primary/40 p-5">
          <h2 id="charge-heading" className="font-semibold">
            {t("locations.addBranch.chargeTitle")}
          </h2>
          <p className="text-sm">
            {t("locations.addBranch.chargeBody", {
              price: money(preview.extra_branch_price),
              before: money(preview.monthly_extra_now),
              after: money(preview.monthly_extra_after),
            })}
          </p>
          <p className="text-xs text-muted">{t("locations.addBranch.chargeNote")}</p>
        </section>
      )}
      <NewBranchForm
        action={addBranch}
        chargeable={preview.chargeable}
        branches={locations.filter((l) => l.active).map((l) => ({ id: l.id, name: l.name }))}
        people={people}
      />
    </main>
  );
}
