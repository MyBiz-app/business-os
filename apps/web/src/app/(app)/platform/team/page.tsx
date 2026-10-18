import { ShieldCheck } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { BRAND } from "@business-os/i18n/brand";

import { unwrap } from "@/lib/api";
import { getPlatformFor } from "@/lib/platform";

import { AddStaffForm, StaffRow } from "./staff-forms";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("platform.team");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** MyBiz's own team: levels, permissions, pausing and removing. The database enforces the
 * rules; the page only offers what this person may do. */
export default async function PlatformTeamPage() {
  const t = await getTranslations("platform.team");
  const { api, staff, isOwner } = await getPlatformFor("staff.manage");
  const team = unwrap(await api.GET("/platform/staff"));
  const actor = {
    levels: isOwner ? (["owner", "manager", "employee"] as const) : (["employee"] as const),
    permissions: staff.permissions,
  };
  const manageable = (level: string, email: string) =>
    email !== staff.email && level !== "primary_owner" && (isOwner || level === "employee");

  return (
    <Container as="main" size="settings" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader title={t("title")} description={t("subtitle")} />
      <p className="flex items-start gap-2 rounded-xl bg-primary/10 px-4 py-3 text-sm">
        <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-primary-ink" />
        {t("rules")}
      </p>
      <section aria-labelledby="team-list" className="flex flex-col gap-3">
        <h2 id="team-list" className="sr-only">
          {t("title")}
        </h2>
        <ul className="card">
          {team.map((member) => (
            <StaffRow
              key={`${member.email}-${member.level}-${member.permissions.join()}-${member.disabled}`}
              member={member}
              actor={{ levels: [...actor.levels], permissions: actor.permissions }}
              manageable={manageable(member.level, member.email)}
            />
          ))}
        </ul>
      </section>
      <section aria-labelledby="add-heading" className="card flex flex-col gap-4 p-6">
        <h2 id="add-heading" className="text-lg font-semibold">
          {t("add")}
        </h2>
        <AddStaffForm actor={{ levels: [...actor.levels], permissions: actor.permissions }} />
      </section>
    </Container>
  );
}
