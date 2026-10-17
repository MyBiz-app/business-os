import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { apiAssetUrl } from "@/lib/api";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";
import { coverSrc } from "@/lib/workspace";

import { TopicHeader } from "../topic-header";
import { BrandingEditor } from "./branding-editor";

/** Settings → Branding: set the name, color, logo and cover on one side and see them live on the other. */
export default async function BrandingSettingsPage() {
  const t = await getTranslations("settings");
  const { tenant } = await getTenant();
  if (!canManageSettings(tenant)) redirect("/dashboard");

  return (
    <div className="flex flex-col gap-6">
      <TopicHeader title={t("nav.items.branding")} description={t("nav.hints.branding")} />
      <BrandingEditor
        key={`${tenant.name}-${tenant.primary_color}-${tenant.logo_url}-${tenant.cover_url}`}
        name={tenant.name}
        color={tenant.primary_color ?? null}
        logo={apiAssetUrl(tenant.logo_url) ?? null}
        cover={tenant.cover_url ? coverSrc(tenant.cover_url) : null}
      />
    </div>
  );
}
