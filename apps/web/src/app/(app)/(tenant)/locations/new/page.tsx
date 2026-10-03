import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { canWriteCatalog } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { createLocation } from "../actions";
import { LocationForm } from "../location-form";

export default async function NewLocationPage() {
  const t = await getTranslations();
  const { tenant } = await getTenant();
  if (!canWriteCatalog(tenant.role)) redirect("/locations");

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <h1 className="text-3xl font-bold">{t("locations.new")}</h1>
      <LocationForm action={createLocation} submitLabel={t("common.create")} />
    </main>
  );
}
