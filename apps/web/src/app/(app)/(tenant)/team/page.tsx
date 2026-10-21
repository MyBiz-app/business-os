import { getLocale, getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { avatarSrc } from "@/components/avatar";
import { unwrap } from "@/lib/api";
import { canManageTeam } from "@/lib/permissions";
import { getBranches, getTenant } from "@/lib/tenant";

import { revokeInvitation } from "./actions";
import { InviteButton, MemberRow } from "./team-forms";
import { StaffCardWindow } from "./staff-card-window";
import { openedId, withOpen } from "@/lib/open-window";
import { TeamTabs } from "./team-tabs";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

export default async function TeamPage({ searchParams }: PageProps<"/team">) {
  const query = await searchParams;
  const t = await getTranslations();
  const locale = await getLocale();
  const { me, tenant, api, scope } = await getTenant();
  const branches = await getBranches();
  if (!canManageTeam(tenant)) redirect("/dashboard");
  const openedMember = openedId(query);

  const [team, roles] = await Promise.all([
    api.GET("/staff", { params: scope }).then(unwrap),
    api.GET("/roles", { params: scope }).then(unwrap),
  ]);
  const isOwner = tenant.role === "owner";
  const formatDate = (iso: string) =>
    new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: tenant.time_zone }).format(new Date(iso));

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <TeamTabs active="members" tenant={tenant} />
      <PageHeader title={t("team.title")} description={t("team.subtitle")} actions={<InviteButton allowOwner={isOwner} />} />

      <section aria-labelledby="members-heading" className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between gap-3">
          <h2 id="members-heading" className="text-lg font-semibold">
            {t("team.members")}
          </h2>
          <span className="text-sm text-muted">{t("team.count", { count: team.members.length })}</span>
        </div>
        <ul className="card overflow-hidden">
          {team.members.map((member) => (
            <MemberRow
              key={`${member.user_id}-${member.role}-${member.custom_role_id}`}
              userId={member.user_id}
              email={member.email}
              name={member.full_name}
              role={member.role}
              customRoleId={member.custom_role_id}
              customRoles={roles.custom.map(({ id, name }) => ({ id, name }))}
              isSelf={member.user_id === me.id}
              allowOwner={isOwner}
              branches={branches}
              memberBranches={member.location_ids}
              homeBranch={member.home_location_id ?? null}
              avatar={avatarSrc(member.user_id, member.avatar_url)}
              title={member.job_title ?? null}
              allPermissions={roles.permissions}
              permissions={member.permissions}
              openHref={withOpen("/team", query, member.user_id)}
            />
          ))}
        </ul>
      </section>

      <section aria-labelledby="pending-heading" className="flex flex-col gap-3">
        <h2 id="pending-heading" className="text-lg font-semibold">
          {t("team.pending")}
        </h2>
        {team.invitations.length === 0 ? (
          <p className="text-sm text-muted">{t("team.noPending")}</p>
        ) : (
          <ul className="card">
            {team.invitations.map((invitation) => (
              <li key={invitation.id} className="flex flex-wrap items-center gap-3 border-t border-border px-4 py-3 first:border-t-0">
                <span className="flex-1 truncate" dir="ltr">
                  {invitation.email}
                </span>
                <span className="text-sm text-muted">{t(`roles.${invitation.role}`)}</span>
                <span className="text-sm text-muted">
                  {invitation.status === "expired" ? t("team.expired") : t("team.expires", { date: formatDate(invitation.expires_at) })}
                </span>
                {(isOwner || invitation.role !== "owner") && (
                  <form action={revokeInvitation.bind(null, invitation.id)}>
                    <button type="submit" className="btn-link text-sm text-danger underline-offset-4 hover:underline">
                      {t("team.revoke")}
                    </button>
                  </form>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
      {openedMember && <StaffCardWindow id={openedMember} tab={query.tab} closeHref={withOpen("/team", {}, null)} tabBase={withOpen("/team", {}, openedMember)} />}
    </Container>
  );
}
