import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { BRAND } from "@business-os/i18n/brand";

import { Avatar, avatarSrc } from "@/components/avatar";
import { BackLink } from "@/components/back-link";
import { Container } from "@/components/layout/container";
import { LinkSegmented } from "@/components/ui/link-segmented";
import { unwrap } from "@/lib/api";
import { isolate } from "@/lib/bidi";
import { canManageAI, canReadPayroll } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { AiTab, AvailabilityTab, DocumentsTab, EmploymentTab, OverviewTab, PermissionsTab } from "./card-sections";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("staffCard");
  return { title: `${t("title")} · ${BRAND.name}` };
}

const TABS = ["overview", "employment", "availability", "documents", "ai", "permissions"] as const;
type Tab = (typeof TABS)[number];

/** One team member in one place: who they are, when they work, their pay file, documents, AI
 * use and what they may do. Every tab shows only for those who may see it; the API still refuses
 * what the viewer is not allowed to read. */
export default async function StaffCardPage({ params, searchParams }: PageProps<"/team/[userId]">) {
  const { userId } = await params;
  const query = await searchParams;
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
  const active: Tab = visible.find((tab) => tab === query.tab) ?? "overview";
  const name = member.full_name ?? member.email;
  const href = (tab: Tab) => (tab === "overview" ? `/team/${userId}` : `/team/${userId}?tab=${tab}`);

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/team" label={tAll("team.title")} />
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
    </Container>
  );
}
