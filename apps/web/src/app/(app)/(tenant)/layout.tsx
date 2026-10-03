import { getTranslations } from "next-intl/server";
import Image from "next/image";

import { type NavItem, SideNav } from "@/components/side-nav";
import { apiAssetUrl } from "@/lib/api";
import { brandStyle } from "@/lib/brand";
import { canManageSettings, canManageTeam, canUseAssistant } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

export default async function TenantLayout({ children }: LayoutProps<"/">) {
  const { tenant } = await getTenant();
  const t = await getTranslations();
  const logo = apiAssetUrl(tenant.logo_url);

  const items: NavItem[] = [
    { href: "/dashboard", label: t("nav.dashboard") },
    ...(canUseAssistant(tenant.role) ? [{ href: "/assistant", label: t("nav.assistant") }] : []),
    { href: "/schedule", label: t("nav.schedule") },
    { href: "/clients", label: t(`terms.${tenant.vertical}.clients` as "terms.fitness.clients") },
    { href: "/services", label: t("nav.services") },
    { href: "/plans", label: t("nav.plans") },
    { href: "/locations", label: t("nav.locations") },
  ];
  if (canManageTeam(tenant.role)) items.push({ href: "/team", label: t("nav.team") });
  if (canManageSettings(tenant.role)) items.push({ href: "/settings", label: t("nav.settings") });

  return (
    // The business's brand color replaces the product color inside its own area.
    <div style={brandStyle(tenant.primary_color)} className="flex flex-1 flex-col md:flex-row">
      <aside className="border-b border-border md:w-60 md:shrink-0 md:border-b-0 md:border-e">
        <div className="flex items-center gap-3 px-6 py-4">
          {logo ? (
            <Image src={logo} alt="" width={36} height={36} unoptimized className="size-9 rounded-lg object-contain" />
          ) : (
            <span aria-hidden="true" className="flex size-9 items-center justify-center rounded-lg bg-primary font-bold text-on-primary">
              {tenant.name.slice(0, 1)}
            </span>
          )}
          <span dir="auto" className="truncate font-semibold">{tenant.name}</span>
        </div>
        <SideNav items={items} />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </div>
  );
}
