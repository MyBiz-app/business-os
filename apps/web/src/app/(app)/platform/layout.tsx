import { ShieldCheck } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { type NavItem, SideNav } from "@/components/side-nav";
import { getPlatform } from "@/lib/platform";

/** The MyBiz console: its own menu, showing only what the team member's permissions allow. */
export default async function PlatformLayout({ children }: LayoutProps<"/platform">) {
  const t = await getTranslations("platform");
  const { staff, can, isOwner } = await getPlatform();
  const items: (NavItem & { show: boolean })[] = [
    { href: "/platform", label: t("nav.overview"), icon: "dashboard", show: true },
    { href: "/platform/businesses", label: t("nav.businesses"), icon: "businesses", show: can("businesses.read") },
    { href: "/platform/inbox", label: t("nav.inbox"), icon: "inbox", show: can("inbox.manage") },
    { href: "/platform/billing", label: t("nav.billing"), icon: "billing", show: can("billing.manage") },
    { href: "/platform/team", label: t("nav.team"), icon: "team", show: can("staff.manage") },
    { href: "/platform/integrations", label: t("nav.integrations"), icon: "integrations", show: isOwner },
    { href: "/platform/audit", label: t("nav.audit"), icon: "audit", show: isOwner },
  ];

  return (
    <div className="flex flex-1 flex-col md:flex-row">
      <aside className="border-b border-border bg-surface/60 backdrop-blur print:hidden md:sticky md:top-16 md:h-[calc(100dvh-4rem)] md:w-64 md:shrink-0 md:overflow-y-auto md:border-b-0 md:border-e">
        <div className="mx-3 my-3 flex items-center gap-3 rounded-2xl px-3 py-3">
          <span aria-hidden="true" className="flex size-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-from to-brand-to text-white shadow-md">
            <ShieldCheck className="size-5" />
          </span>
          <span className="flex min-w-0 flex-col">
            <span className="truncate font-semibold">{t("console")}</span>
            <span className="truncate text-xs text-muted">{t("you", { level: t(`levels.${staff.level}`) })}</span>
          </span>
        </div>
        <SideNav label={t("nav.label")} items={items.filter((item) => item.show).map(({ href, label, icon }) => ({ href, label, icon }))} />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </div>
  );
}
