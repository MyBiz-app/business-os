import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { canManageTeam } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { revokeInvitation } from "./actions";
import { InviteForm, MemberRow } from "./team-forms";

export default async function TeamPage() {
  const t = await getTranslations();
  const locale = await getLocale();
  const { me, tenant, api, scope } = await getTenant();
  if (!canManageTeam(tenant)) redirect("/dashboard");

  const [team, roles] = await Promise.all([
    api.GET("/staff", { params: scope }).then(unwrap),
    api.GET("/roles", { params: scope }).then(unwrap),
  ]);
  const isOwner = tenant.role === "owner";
  const formatDate = (iso: string) =>
    new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: tenant.time_zone }).format(new Date(iso));

  return (
    <main className="enter mx-auto flex w-full max-w-4xl flex-1 flex-col gap-8 px-6 py-10">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold">{t("team.title")}</h1>
        <p className="text-sm text-muted">{t("team.subtitle")}</p>
        <Link href="/team/roles" className="mt-1 text-sm text-primary underline-offset-4 hover:underline">
          {t("team.manageRoles")}
        </Link>
      </div>

      <section aria-labelledby="members-heading" className="flex flex-col gap-3">
        <h2 id="members-heading" className="text-lg font-semibold">
          {t("team.members")}
        </h2>
        <ul className="card">
          {team.members.map((member) => (
            <MemberRow
              key={`${member.user_id}-${member.role}-${member.custom_role_id}`}
              userId={member.user_id}
              email={member.email}
              role={member.role}
              customRoleId={member.custom_role_id}
              customRoles={roles.custom.map(({ id, name }) => ({ id, name }))}
              isSelf={member.user_id === me.id}
              allowOwner={isOwner}
            />
          ))}
        </ul>
      </section>

      <section aria-labelledby="invite-heading" className="flex flex-col gap-4 card p-6">
        <h2 id="invite-heading" className="text-lg font-semibold">
          {t("team.invite")}
        </h2>
        <InviteForm allowOwner={isOwner} />
      </section>

      <section aria-labelledby="pending-heading" className="flex flex-col gap-3">
        <h2 id="pending-heading" className="text-lg font-semibold">
          {t("team.pending")}
        </h2>
        {team.invitations.length === 0 ? (
          <p className="text-sm text-muted">{t("team.noPending")}</p>
        ) : (
          <ul className="rounded-2xl border border-border">
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
                    <button type="submit" className="text-sm text-danger underline-offset-4 hover:underline">
                      {t("team.revoke")}
                    </button>
                  </form>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
