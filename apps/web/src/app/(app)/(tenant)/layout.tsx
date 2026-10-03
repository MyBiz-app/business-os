import { getTranslations } from "next-intl/server";

import { type NavItem, SideNav } from "@/components/side-nav";
import { canManageTeam } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

export default async function TenantLayout({ children }: LayoutProps<"/">) {
  const { tenant } = await getTenant();
  const t = await getTranslations();

  const items: NavItem[] = [
    { href: "/dashboard", label: t("nav.dashboard") },
    { href: "/clients", label: t(`terms.${tenant.vertical}.clients` as "terms.fitness.clients") },
    { href: "/services", label: t("nav.services") },
    { href: "/locations", label: t("nav.locations") },
  ];
  if (canManageTeam(tenant.role)) items.push({ href: "/team", label: t("nav.team") });

  return (
    <div className="flex flex-1 flex-col md:flex-row">
      <SideNav items={items} />
      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </div>
  );
}
