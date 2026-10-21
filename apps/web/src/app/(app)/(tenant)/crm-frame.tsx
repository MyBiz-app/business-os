import type { ReactNode } from "react";

import { ScopedMessages } from "@/components/scoped-messages";
import { getTranslations } from "next-intl/server";
import { cookies } from "next/headers";
import Link from "next/link";
import { termsOf, vertical } from "@business-os/verticals";

import { type NavChild, type NavItem, SideNav } from "@/components/side-nav";
import { apiAssetUrl } from "@/lib/api";
import { isolate } from "@/lib/bidi";
import { brandStyle } from "@/lib/brand";
import { lockedMenuMode } from "@/lib/nav-capabilities";
import { isSolo, SOLO_MAX_UPGRADES, visibleTopics } from "@/lib/solo";
import { canManageSettings, canManageTeam, canReadPayroll, canUseAssistant } from "@/lib/permissions";
import { hasUpgrade, type Upgrade } from "@/lib/upgrades";
import { getBranches, getTenant, hasBookableRooms } from "@/lib/tenant";

import { leaveSupport } from "../platform/actions";
import { tabOrder } from "./catalog/tabs";
import { topicsFor } from "./settings/topics";
import { CrmAside, NAV_TONE_COOKIE } from "./_menu/crm-aside";
import { WorkspaceSwitcher } from "./_menu/workspace-switcher";
import { AiBubble } from "./ai-bubble/ai-bubble";
import { ScreenContextProvider } from "./ai-bubble/screen-context";
import "./crm-shell.css";

/** The CRM frame (side menu, branch switcher, banners, AI bubble) around whatever page it wraps. */
export async function CrmFrame({ children, modal }: { children: ReactNode; modal?: ReactNode }) {
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
  const sub = (key: string) => t(`nav.sub.${key}` as "nav.sub.people");
  const clientAppLocked = !hasUpgrade(tenant.modules, "client_app");
  const solo = isSolo(tenant);
  // Missing capabilities are grey items for the first 30 days, then fold into one "Add capabilities".
  const folded = lockedMenuMode(tenant.created_at) === "folded";
  const candidates: (NavItem & { permission?: string; upgrade?: Upgrade })[] = [
    { href: "/dashboard", group: g("overview"), label: t("nav.dashboard"), icon: "dashboard" },
    { href: "/reports", group: g("overview"), label: t("nav.reports"), icon: "reports", permission: "reports.read",
      children: [
        { href: "/reports", label: t("nav.reports") },
        { href: "/reports/map", label: t("nav.insightsMap") },
        ...(solo ? [] : [{ href: "/locations/map", label: t("nav.branchMap") }]),
      ],
    },
    {
      href: "/ai", group: g("overview"), label: t("nav.assistant"), icon: "assistant", permission: "ai.use", upgrade: "ai",
      children: [{ href: "/ai#ai-team", label: sub("aiTeam") }, { href: "/ai#ai-tasks", label: sub("aiTasks") }],
    },
    { href: "/schedule", group: g("work"), label: t(`terms.${termsOf(tenant.vertical)}.schedule` as "terms.fitness.schedule"), icon: "schedule", permission: "schedule.read" },
    ...(rents ? [{ href: "/resources", group: g("work"), label: t("nav.resources"), icon: "resources" as const, permission: "schedule.read" }] : []),
    { href: "/clients", group: g("clients"), label: t(`terms.${termsOf(tenant.vertical)}.clients` as "terms.fitness.clients"), icon: "clients", permission: "clients.read",
      children: [
        { href: "/clients", label: sub("clientList") },
        ...(clientAppLocked
          ? folded ? [] : [{ href: "/upgrade/client_app", label: t("nav.clientApp"), locked: true }]
          : [{ href: "/clients/join", label: t("nav.clientApp") }]),
        { href: "/clients/import", label: sub("clientImport") },
      ],
    },
    { href: "/leads", group: g("clients"), label: t("nav.leads"), icon: "leads", permission: "clients.read", upgrade: "crm" },
    { href: "/messages", group: g("clients"), label: t("nav.messages"), icon: "messages", permission: "clients.read", upgrade: "whatsapp" },
    { href: "/content", group: g("clients"), label: t("nav.content"), icon: "content", permission: "social.read", upgrade: "social" },
    { href: "/catalog", group: g("catalog"), label: t("nav.catalog"), icon: "catalog", permission: "catalog.read",
      children: tabOrder(tenant.booking_requires_plan).map((key) => ({ href: `/catalog?tab=${key}`, label: t(`catalog.tabs.${key}`) })),
    },
    { href: "/quotes", group: g("money"), label: t(termsOf(tenant.vertical) === "events" ? "nav.quotesEvents" : "nav.quotes"), icon: "quotes", permission: "clients.read" },
    { href: "/invoices", group: g("money"), label: t("nav.invoices"), icon: "invoices", permission: "sales.manage" },
    ...(vertical(tenant.vertical)?.timeBilling
      ? [
          { href: "/time", group: g("work"), label: t("nav.time"), icon: "time" as const, permission: "clients.read" },
          { href: "/bills", group: g("money"), label: t("nav.billingRun"), icon: "billing" as const, permission: "sales.manage" },
        ]
      : []),
    { href: "/sales", group: g("money"), label: t("nav.sales"), icon: "sales", permission: "reports.read",
      children: [{ href: "/sales", label: t("nav.sales") }, { href: "/sales/orders", label: sub("orders") }],
    },
    ...(solo ? [] : [{ href: "/locations", group: g("business"), label: t("nav.locations"), icon: "locations" as const, permission: "catalog.read" }]),
    { href: "/files", group: g("business"), label: t("nav.files"), icon: "files", permission: "files.read" },
    { href: "/website", group: g("business"), label: t("nav.website"), icon: "website", permission: "business.settings" },
    { href: "/migration", group: g("business"), label: t("nav.migration"), icon: "migration", permission: "migration.manage" },
  ];
  // Modules the business doesn't have stay in the menu, locked, and open a preview.
  let upgradeOffers = 0;
  const items: NavItem[] = candidates
    .filter((item) => !item.permission || allowed(item.permission))
    // Solo mode: at most two suggestions to upgrade, the rest stay out of the menu.
    .filter((item) => {
      if (!solo || !item.upgrade || hasUpgrade(tenant.modules, item.upgrade)) return true;
      upgradeOffers += 1;
      return upgradeOffers <= SOLO_MAX_UPGRADES;
    })
    .map(({ href, label, icon, upgrade, group, children }) =>
      upgrade && !hasUpgrade(tenant.modules, upgrade) ? { href: `/upgrade/${upgrade}`, label, icon, group, locked: true } : { href, label, icon, group, children },
    );
  if (folded) {
    const hidden = items.filter((item) => item.locked).length > 0 || clientAppLocked;
    const kept = items.filter((item) => !item.locked);
    items.length = 0;
    items.push(...kept);
    if (hidden && canManageSettings(tenant)) {
      items.push({ href: "/upgrade", label: t("nav.addCapabilities"), icon: "capabilities", group: g("business") });
    }
  }
  // A sub-item shows only if the user may open its page.
  const teamChildren: NavChild[] = [
    { href: "/team", label: sub("people") },
    { href: "/team/organization", label: sub("organization") },
    { href: "/team/shifts", label: sub("shifts") },
    { href: "/team/time-off", label: sub("timeOff") },
    { href: "/team/shift-swaps", label: sub("shiftSwaps") },
    ...(allowed("time.approve") ? [{ href: "/team/time-clock", label: sub("timeClock") }] : []),
    ...(canReadPayroll(tenant) ? [{ href: "/team/payroll", label: sub("payroll") }] : []),
    ...(canReadPayroll(tenant) || allowed("payroll.propose") ? [{ href: "/team/bonuses", label: sub("bonuses") }] : []),
    { href: "/team/roles", label: sub("roles") },
  ];
  const settingsChildren: NavChild[] = visibleTopics(topicsFor(tenant.role), solo)
    .map(({ key, href }) => ({ href, label: t(`settings.nav.items.${key}` as "settings.nav.items.business") }));
  if (!solo && canManageTeam(tenant)) items.push({ href: "/team", label: t("nav.team"), icon: "team", group: g("business"), children: teamChildren });
  if (canManageSettings(tenant)) items.push({ href: "/settings", label: t("nav.settings"), icon: "settings", group: g("business"), children: settingsChildren });

  // Items of one section sit together (the sort is stable, so the order inside a section stays).
  const rank = (item: NavItem) => order.findIndex((key) => g(key) === item.group);
  items.sort((a, b) => rank(a) - rank(b));

  // The floating AI chat: for whoever may use the assistant, in a business that has the AI module.
  const navTone = (await cookies()).get(NAV_TONE_COOKIE)?.value === "dark" ? "dark" : "light";
  const aiBubble = canUseAssistant(tenant) && tenant.modules.some((m) => m === "ai_basic" || m === "ai_pro");

  // The business's brand color replaces the product color inside its own area.
  return (
    <ScopedMessages scopes={["app", "tenant"]}>
    <ScreenContextProvider>
    <div style={brandStyle(brandColor)} className="brand flex flex-1 flex-col md:flex-row">
      <CrmAside initial={navTone} labels={{ light: t("nav.sidebarLight"), dark: t("nav.sidebarDark") }}>
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
      </CrmAside>
      {/* The floating AI chat sits over the bottom corner: leave it room so it never hides content. */}
      <div className={`crm-content flex min-w-0 flex-1 flex-col ${aiBubble ? "pb-24 print:pb-0" : ""}`}>
        {(tenant.role === "support" || tenant.role === "platform") && (
          <div
            role="status"
            className={`flex flex-wrap items-center justify-between gap-2 border-b px-6 py-2 text-sm ${
              tenant.role === "platform" ? "border-warning/50 bg-warning/10 font-medium" : "border-border bg-surface"
            }`}
          >
            <span>{tenant.role === "platform" ? t("support.actBanner", { name: isolate(tenant.name) }) : t("support.banner")}</span>
            <form action={leaveSupport}>
              <button type="submit" className="btn-link font-medium text-primary-ink underline-offset-4 hover:underline">
                {tenant.role === "platform" ? t("support.actLeave") : t("support.leave")}
              </button>
            </form>
          </div>
        )}
        {tenant.billing_state === "read_only" && (
          <div role="status" className="flex flex-wrap items-center justify-between gap-2 border-b border-danger/40 bg-danger/10 px-6 py-2 text-sm font-medium">
            <span>{t("billing.collection.banner")}</span>
            {canManageSettings(tenant) && (
              <Link href="/settings/billing" className="font-semibold text-primary-ink underline-offset-4 hover:underline">
                {t("billing.collection.bannerOwner")}
              </Link>
            )}
          </div>
        )}
        {children}
      </div>
    </div>
    {aiBubble && <AiBubble />}
    {/* Forms that open as a window over the page (round 7); the slot is empty otherwise. */}
    {modal}
    </ScreenContextProvider>
    </ScopedMessages>
  );
}
