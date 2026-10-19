import { getTranslations } from "next-intl/server";

import { LinkSegmented } from "@/components/ui/link-segmented";
import { canReadPayroll } from "@/lib/permissions";
import type { getTenant } from "@/lib/tenant";

export type TeamTab = "members" | "shifts" | "timeOff" | "timeClock" | "swaps" | "payroll" | "bonuses" | "organization" | "roles";

type Tenant = Awaited<ReturnType<typeof getTenant>>["tenant"];

/** The one tab strip shared by every page of the team area, so you always see where you are.
 * A tab shows only for those who may open it. */
export async function TeamTabs({ active, tenant }: { active: TeamTab; tenant: Tenant }) {
  const t = await getTranslations("team");
  const tc = await getTranslations("common");
  const tabs: { key: TeamTab; href: string; show: boolean }[] = [
    { key: "members", href: "/team", show: true },
    { key: "shifts", href: "/team/shifts", show: true },
    { key: "timeOff", href: "/team/time-off", show: true },
    { key: "timeClock", href: "/team/time-clock", show: tenant.permissions.includes("time.approve") },
    { key: "swaps", href: "/team/shift-swaps", show: true },
    { key: "payroll", href: "/team/payroll", show: canReadPayroll(tenant) },
    { key: "bonuses", href: "/team/bonuses", show: canReadPayroll(tenant) || tenant.permissions.includes("payroll.propose") },
    { key: "organization", href: "/team/organization", show: true },
    { key: "roles", href: "/team/roles", show: true },
  ];
  return (
    <div className="overflow-x-auto pb-1">
      <div className="w-max min-w-full">
        <LinkSegmented
          label={t("tabsLabel")}
          loadingLabel={tc("loading")}
          active={active}
          options={tabs.filter((tab) => tab.show).map((tab) => ({ key: tab.key, label: t(`tabs.${tab.key}`), href: tab.href }))}
        />
      </div>
    </div>
  );
}
