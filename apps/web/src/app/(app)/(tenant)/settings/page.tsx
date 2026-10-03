import { getTranslations } from "next-intl/server";
import Image from "next/image";
import { redirect } from "next/navigation";

import { apiAssetUrl } from "@/lib/api";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { removeLogo } from "./actions";
import { BrandColorForm, DetailsForm, LogoForm } from "./settings-forms";

export default async function SettingsPage() {
  const t = await getTranslations("settings");
  const { tenant } = await getTenant();
  if (!canManageSettings(tenant.role)) redirect("/dashboard");
  const logo = apiAssetUrl(tenant.logo_url);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-6 py-10">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <p className="text-sm text-muted">{t("subtitle")}</p>
      </div>

      <section aria-labelledby="details-heading" className="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-6">
        <h2 id="details-heading" className="text-lg font-semibold">
          {t("details")}
        </h2>
        <DetailsForm tenant={tenant} timeZones={Intl.supportedValuesOf("timeZone")} />
      </section>

      <section aria-labelledby="brand-heading" className="flex flex-col gap-6 rounded-2xl border border-border bg-surface p-6">
        <div className="flex flex-col gap-1">
          <h2 id="brand-heading" className="text-lg font-semibold">
            {t("brand")}
          </h2>
          <p className="text-sm text-muted">{t("brandHint")}</p>
        </div>
        <BrandColorForm key={tenant.primary_color ?? "default"} color={tenant.primary_color} />

        <div className="flex flex-col gap-3 border-t border-border pt-6">
          <h3 className="font-semibold">{t("logo")}</h3>
          <div className="flex items-center gap-4">
            {logo ? (
              <Image src={logo} alt={t("preview")} width={64} height={64} unoptimized className="size-16 rounded-xl border border-border bg-background object-contain" />
            ) : (
              <span className="text-sm text-muted">{t("noLogo")}</span>
            )}
            {logo && (
              <form action={removeLogo}>
                <button type="submit" className="text-sm text-danger underline-offset-4 hover:underline">
                  {t("removeLogo")}
                </button>
              </form>
            )}
          </div>
          <LogoForm key={tenant.logo_url ?? "none"} />
        </div>
      </section>
    </main>
  );
}
