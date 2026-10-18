import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";

import { Avatar, avatarSrc } from "@/components/avatar";
import { LinkSegmented } from "@/components/ui/link-segmented";
import { unwrap } from "@/lib/api";
import { isolate } from "@/lib/bidi";
import { canManageAI, canReadPayroll } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { AiTab, AvailabilityTab, DocumentsTab, EmploymentTab, OverviewTab, PermissionsTab } from "./card-sections";

const TABS = ["overview", "employment", "availability", "documents", "ai", "permissions"] as const;
type Tab = (typeof TABS)[number];

/** One team member in one place: who they are, when they work, their pay file, documents, AI
 * use and what they may do. Every tab shows only for those who may see it; the API still refuses
 * what the viewer is not allowed to read. The page and the window over the team list show the
 * same thing. */
export async function StaffCardBody({ userId, tab: requestedTab, tabBase }: { userId: string; tab?: string | string[]; tabBase?: string }) {
  const t = await getTranslations("staffCard");
  const tc = await getTranslations("common");
  const tAll = await getTranslations();
  const context = await getTenantFor("staff.manage");
  const { api, scope, tenant, me } = context;
  const team = unwrap(await api.GET("/staff", { params: scope }));
  const member = team.members.find((m) => m.user_id === userId);
  if (!member) notFound();

  const visible: Tab[] = TABS.filter((tab) => {
    if (tab === "employment" || tab === "documents") return canReadPayroll(tenant);
    if (tab === "ai") return canManageAI(tenant);
    return true;
  });
  const active: Tab = visible.find((tab) => tab === requestedTab) ?? "overview";
  const name = member.full_name ?? member.email;
  // As a page the tabs live at /team/<id>?tab=...; in a window over the list they keep the window open.
  const href = (tab: Tab) => (tabBase ? `${tabBase}${tabBase.includes("?") ? "&" : "?"}tab=${tab}` : tab === "overview" ? `/team/${userId}` : `/team/${userId}?tab=${tab}`);

  return (
    <div className="flex flex-1 flex-col gap-6">
      <header className="flex flex-wrap items-center gap-4">
        <Avatar id={userId} name={name} size="xl" src={avatarSrc(userId, member.avatar_url)} />
        <div className="flex min-w-0 flex-col gap-1">
          <h1 className="text-3xl font-extrabold tracking-tight text-balance sm:text-4xl" dir="auto">
            {isolate(name)} {userId === me.id && <span className="text-lg font-normal text-muted">{tAll("team.you")}</span>}
          </h1>
          <p className="text-base text-muted" dir="auto">
            {[member.job_title, member.custom_role_name ?? tAll(`roles.${member.role}` as "roles.staff")].filter(Boolean).join(" · ")}
          </p>
        </div>
      </header>
      <div className="overflow-x-auto pb-1">
        <LinkSegmented
          label={t("tabsLabel")}
          loadingLabel={tc("loading")}
          active={active}
          options={visible.map((tab) => ({ key: tab, label: t(`tabs.${tab}`), href: href(tab) }))}
        />
      </div>
      {active === "overview" && <OverviewTab member={member} context={context} />}
      {active === "employment" && <EmploymentTab member={member} context={context} />}
      {active === "availability" && <AvailabilityTab member={member} context={context} />}
      {active === "documents" && <DocumentsTab member={member} context={context} />}
      {active === "ai" && <AiTab member={member} context={context} />}
      {active === "permissions" && <PermissionsTab member={member} context={context} />}
    </div>
  );
}
