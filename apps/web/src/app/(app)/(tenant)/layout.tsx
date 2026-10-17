import { ScopedMessages } from "@/components/scoped-messages";
import { getTranslations } from "next-intl/server";
import { termsOf, vertical } from "@business-os/verticals";

import { type NavItem, SideNav } from "@/components/side-nav";
import { apiAssetUrl } from "@/lib/api";
import { isolate } from "@/lib/bidi";
import { brandStyle } from "@/lib/brand";
import { canManageSettings, canManageTeam, canUseAssistant } from "@/lib/permissions";
import { hasUpgrade, type Upgrade } from "@/lib/upgrades";
import { getBranches, getTenant, hasBookableRooms } from "@/lib/tenant";

import { leaveSupport } from "../platform/actions";
import { WorkspaceSwitcher } from "./_menu/workspace-switcher";
import { AiBubble } from "./ai-bubble/ai-bubble";
import { ScreenContextProvider } from "./ai-bubble/screen-context";

export default async function TenantLayout({ children }: LayoutProps<"/">) {
  const { tenant, me, branch } = await getTenant();
  const t = await getTranslations();
  const logo = apiAssetUrl(tenant.logo_url);
  // The branch picker appears once the business has more than one active branch.
  const [branches, rents] = await Promise.all([getBranches(), hasBookableRooms()]);
  const currentBranch = branches.find((b) => b.id === branch) ?? null;
  // A selected branch shows its own logo and color, else the network's.
  const brandColor = currentBranch ? currentBranch.color : tenant.primary_color;
  const brandLogo = currentBranch ? currentBranch.logo : logo;

  // Only what the user's permissions let them open.
  const allowed = (permission: string) => tenant.permissions.includes(permission);
  const order = ["overview", "work", "clients", "catalog", "money", "business"] as const;
  const g = (key: (typeof order)[number]) => t(`nav.groups.${key}`);
  const candidates: (NavItem & { permission?: string; upgrade?: Upgrade })[] = [
    { href: "/dashboard", group: g("overview"), label: t("nav.dashboard"), icon: "dashboard" },
    { href: "/reports", group: g("overview"), label: t("nav.reports"), icon: "reports", permission: "reports.read" },
    { href: "/ai", group: g("overview"), label: t("nav.assistant"), icon: "assistant", permission: "ai.use", upgrade: "ai" },
    { href: "/schedule", group: g("work"), label: t(`terms.${termsOf(tenant.vertical)}.schedule` as "terms.fitness.schedule"), icon: "schedule", permission: "schedule.read" },
    ...(rents ? [{ href: "/resources", group: g("work"), label: t("nav.resources"), icon: "resources" as const, permission: "schedule.read" }] : []),
    { href: "/clients", group: g("clients"), label: t(`terms.${termsOf(tenant.vertical)}.clients` as "terms.fitness.clients"), icon: "clients", permission: "clients.read" },
    { href: "/clients/join", group: g("clients"), label: t("nav.clientApp"), icon: "clientApp", permission: "clients.read", upgrade: "client_app" },
    { href: "/leads", group: g("clients"), label: t("nav.leads"), icon: "leads", permission: "clients.read", upgrade: "crm" },
    { href: "/messages", group: g("clients"), label: t("nav.messages"), icon: "messages", permission: "clients.read", upgrade: "whatsapp" },
    { href: "/content", group: g("clients"), label: t("nav.content"), icon: "content", permission: "social.read", upgrade: "social" },
    { href: "/services", group: g("catalog"), label: t("nav.services"), icon: "services", permission: "catalog.read" },
    { href: "/plans", group: g("catalog"), label: t("nav.plans"), icon: "plans", permission: "catalog.read" },
    { href: "/quotes", group: g("money"), label: t("nav.quotes"), icon: "quotes", permission: "clients.read" },
    { href: "/invoices", group: g("money"), label: t("nav.invoices"), icon: "invoices", permission: "sales.manage" },
    ...(vertical(tenant.vertical)?.timeBilling
      ? [
          { href: "/time", group: g("work"), label: t("nav.time"), icon: "time" as const, permission: "clients.read" },
          { href: "/bills", group: g("money"), label: t("nav.billingRun"), icon: "billing" as const, permission: "sales.manage" },
        ]
      : []),
    { href: "/sales", group: g("money"), label: t("nav.sales"), icon: "sales", permission: "reports.read" },
    { href: "/locations", group: g("business"), label: t("nav.locations"), icon: "locations", permission: "catalog.read" },
    { href: "/files", group: g("business"), label: t("nav.files"), icon: "files", permission: "files.read" },
  ];
  // Modules the business doesn't have stay in the menu, locked, and open a preview.
  const items: NavItem[] = candidates
    .filter((item) => !item.permission || allowed(item.permission))
    .map(({ href, label, icon, upgrade, group }) =>
      upgrade && !hasUpgrade(tenant.modules, upgrade) ? { href: `/upgrade/${upgrade}`, label, icon, group, locked: true } : { href, label, icon, group },
    );
  if (canManageTeam(tenant)) items.push({ href: "/team", label: t("nav.team"), icon: "team", group: g("business") });
  if (canManageSettings(tenant)) items.push({ href: "/settings", label: t("nav.settings"), icon: "settings", group: g("business") });

  // Items of one section sit together (the sort is stable, so the order inside a section stays).
  const rank = (item: NavItem) => order.findIndex((key) => g(key) === item.group);
  items.sort((a, b) => rank(a) - rank(b));

  // The floating AI chat: for whoever may use the assistant, in a business that has the AI module.
  const aiBubble = canUseAssistant(tenant) && tenant.modules.some((m) => m === "ai_basic" || m === "ai_pro");

  // The business's brand color replaces the product color inside its own area.
  return (
    <ScopedMessages scopes={["app", "tenant"]}>
    <ScreenContextProvider>
    <div style={brandStyle(brandColor)} className="brand flex flex-1 flex-col md:flex-row">
      <aside className="nav-dark print:hidden max-md:border-b max-md:border-border md:sticky md:top-16 md:h-[calc(100dvh-4rem)] md:w-64 md:shrink-0 md:overflow-y-auto">
        <WorkspaceSwitcher
          name={tenant.name}
          logo={brandLogo}
          initial={tenant.name.slice(0, 1)}
          current={tenant.id}
          memberships={me.memberships}
          branches={branches.map(({ id, name, ownLogo }) => ({ id, name, logo: ownLogo }))}
          branch={currentBranch?.id ?? null}
        />
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
    {aiBubble && <AiBubble />}
    </ScreenContextProvider>
    </ScopedMessages>
  );
}
