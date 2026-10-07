import { getTranslations } from "next-intl/server";
import { termsOf, vertical } from "@business-os/verticals";

import { type NavItem, SideNav } from "@/components/side-nav";
import { apiAssetUrl } from "@/lib/api";
import { isolate } from "@/lib/bidi";
import { brandStyle } from "@/lib/brand";
import { canManageSettings, canManageTeam } from "@/lib/permissions";
import { hasUpgrade, type Upgrade } from "@/lib/upgrades";
import { getBranches, getTenant, hasBookableRooms } from "@/lib/tenant";

import { leaveSupport } from "../platform/actions";
import { BranchPicker } from "./_menu/branch-picker";
import { BusinessMenu } from "./_menu/business-menu";

export default async function TenantLayout({ children }: LayoutProps<"/">) {
  const { tenant, me, branch } = await getTenant();
  const t = await getTranslations();
  const logo = apiAssetUrl(tenant.logo_url);
  // The branch picker appears once the business has more than one active branch.
  const [branches, rents] = await Promise.all([getBranches(), hasBookableRooms()]);
  const currentBranch = branches.find((b) => b.id === branch) ?? null;

  // Only what the user's permissions let them open.
  const allowed = (permission: string) => tenant.permissions.includes(permission);
  const candidates: (NavItem & { permission?: string; upgrade?: Upgrade })[] = [
    { href: "/dashboard", label: t("nav.dashboard"), icon: "dashboard" },
    { href: "/reports", label: t("nav.reports"), icon: "reports", permission: "reports.read" },
    { href: "/assistant", label: t("nav.assistant"), icon: "assistant", permission: "ai.use", upgrade: "ai" },
    { href: "/schedule", label: t(`terms.${termsOf(tenant.vertical)}.schedule` as "terms.fitness.schedule"), icon: "schedule", permission: "schedule.read" },
    ...(rents ? [{ href: "/resources", label: t("nav.resources"), icon: "resources" as const, permission: "schedule.read" }] : []),
    { href: "/clients", label: t(`terms.${termsOf(tenant.vertical)}.clients` as "terms.fitness.clients"), icon: "clients", permission: "clients.read" },
    { href: "/clients/join", label: t("nav.clientApp"), icon: "clientApp", permission: "clients.read", upgrade: "client_app" },
    { href: "/leads", label: t("nav.leads"), icon: "leads", permission: "clients.read", upgrade: "crm" },
    { href: "/messages", label: t("nav.messages"), icon: "messages", permission: "clients.read", upgrade: "whatsapp" },
    { href: "/services", label: t("nav.services"), icon: "services", permission: "catalog.read" },
    { href: "/plans", label: t("nav.plans"), icon: "plans", permission: "catalog.read" },
    { href: "/quotes", label: t("nav.quotes"), icon: "quotes", permission: "clients.read" },
    ...(vertical(tenant.vertical)?.timeBilling ? [{ href: "/time", label: t("nav.time"), icon: "time" as const, permission: "clients.read" }] : []),
    { href: "/sales", label: t("nav.sales"), icon: "sales", permission: "reports.read" },
    { href: "/locations", label: t("nav.locations"), icon: "locations", permission: "catalog.read" },
  ];
  // Modules the business doesn't have stay in the menu, locked, and open a preview.
  const items: NavItem[] = candidates
    .filter((item) => !item.permission || allowed(item.permission))
    .map(({ href, label, icon, upgrade }) =>
      upgrade && !hasUpgrade(tenant.modules, upgrade) ? { href: `/upgrade/${upgrade}`, label, icon, locked: true } : { href, label, icon },
    );
  if (canManageTeam(tenant)) items.push({ href: "/team", label: t("nav.team"), icon: "team" });
  if (canManageSettings(tenant)) items.push({ href: "/settings", label: t("nav.settings"), icon: "settings" });

  return (
    // The business's brand color replaces the product color inside its own area.
    <div style={brandStyle(tenant.primary_color)} className="brand flex flex-1 flex-col md:flex-row">
      <aside className="border-b border-border bg-surface/60 print:hidden backdrop-blur md:sticky md:top-16 md:h-[calc(100dvh-4rem)] md:w-64 md:shrink-0 md:overflow-y-auto md:border-b-0 md:border-e">
        <BusinessMenu
          name={tenant.name}
          logo={logo}
          current={tenant.id}
          memberships={me.memberships}
          branchName={branches.length > 1 ? (currentBranch?.name ?? t("businessMenu.allBranches")) : null}
        />
        {branches.length > 1 && <BranchPicker current={currentBranch?.id ?? null} branches={branches} />}
        <SideNav items={items} />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        {(tenant.role === "support" || tenant.role === "platform") && (
          <div
            role="status"
            className={`flex flex-wrap items-center justify-between gap-2 border-b px-6 py-2 text-sm ${
              tenant.role === "platform" ? "border-warning/50 bg-warning/10 font-medium" : "border-border bg-surface"
            }`}
          >
            <span>{tenant.role === "platform" ? t("support.actBanner", { name: isolate(tenant.name) }) : t("support.banner")}</span>
            <form action={leaveSupport}>
              <button type="submit" className="font-medium text-primary underline-offset-4 hover:underline">
                {tenant.role === "platform" ? t("support.actLeave") : t("support.leave")}
              </button>
            </form>
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
