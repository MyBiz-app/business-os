import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { BRAND } from "@business-os/i18n/brand";

import { avatarSrc } from "@/components/avatar";
import { BackLink } from "@/components/back-link";
import { unwrap } from "@/lib/api";
import { canManageTeam } from "@/lib/permissions";
import { getBranches, getTenantFor } from "@/lib/tenant";

import { type OrgPerson, OrgChart } from "./org-chart";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("organization");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** Who reports to whom: the business's structure at a glance. Reporting is for the chart only;
 * what each person may do comes from their role. */
export default async function OrganizationPage() {
  const t = await getTranslations();
  const { tenant, api, scope } = await getTenantFor("staff.read");
  const [team, branches] = await Promise.all([api.GET("/staff", { params: scope }).then(unwrap), getBranches()]);
  const branchName = new Map(branches.map((b) => [b.id, b.name]));
  const people: OrgPerson[] = team.members.map((m) => ({
    id: m.user_id,
    name: m.full_name || m.email,
    email: m.email,
    phone: m.phone ?? null,
    title: m.job_title ?? null,
    role: m.custom_role_name ?? t(`roles.${m.role}`),
    isOwner: m.role === "owner",
    reportsTo: m.reports_to ?? null,
    avatar: avatarSrc(m.user_id, m.avatar_url),
    branches: m.location_ids.map((id) => branchName.get(id)).filter((name): name is string => Boolean(name)),
  }));

  return (
    <main className="enter flex w-full flex-1 flex-col gap-6 px-4 py-8 sm:px-6 sm:py-10">
      <div className="flex flex-col gap-2">
        <BackLink href="/team" label={t("team.title")} />
        <h1 className="text-3xl font-bold">{t("organization.title")}</h1>
        <p className="max-w-2xl text-sm text-muted">{t("organization.subtitle")}</p>
      </div>
      <OrgChart people={people} canEdit={canManageTeam(tenant)} />
    </main>
  );
}
