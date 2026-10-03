import { getTranslations } from "next-intl/server";
import Image from "next/image";

import { type NavItem, SideNav } from "@/components/side-nav";
import { apiAssetUrl } from "@/lib/api";
import { brandStyle } from "@/lib/brand";
import { canManageSettings, canManageTeam } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

export default async function TenantLayout({ children }: LayoutProps<"/">) {
  const { tenant } = await getTenant();
  const t = await getTranslations();
  const logo = apiAssetUrl(tenant.logo_url);

  // Only what the user's permissions let them open.
  const allowed = (permission: string) => tenant.permissions.includes(permission);
  const candidates: (NavItem & { permission?: string })[] = [
    { href: "/dashboard", label: t("nav.dashboard") },
    { href: "/assistant", label: t("nav.assistant"), permission: "ai.use" },
    { href: "/schedule", label: t("nav.schedule"), permission: "schedule.read" },
    { href: "/clients", label: t(`terms.${tenant.vertical}.clients` as "terms.fitness.clients"), permission: "clients.read" },
    { href: "/services", label: t("nav.services"), permission: "catalog.read" },
    { href: "/plans", label: t("nav.plans"), permission: "catalog.read" },
    { href: "/locations", label: t("nav.locations"), permission: "catalog.read" },
  ];
  const items: NavItem[] = candidates
    .filter((item) => !item.permission || allowed(item.permission))
    .filter((item) => item.href !== "/assistant" || tenant.modules.some((m) => m === "ai_basic" || m === "ai_pro"))
    .map(({ href, label }) => ({ href, label }));
  if (canManageTeam(tenant)) items.push({ href: "/team", label: t("nav.team") });
  if (canManageSettings(tenant)) items.push({ href: "/settings", label: t("nav.settings") });

  return (
    // The business's brand color replaces the product color inside its own area.
    <div style={brandStyle(tenant.primary_color)} className="brand flex flex-1 flex-col md:flex-row">
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
