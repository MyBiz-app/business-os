import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { canManageTeam } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { RoleForm } from "./role-form";

export default async function RolesPage() {
  const t = await getTranslations("team");
  const { tenant, api, scope } = await getTenant();
  if (!canManageTeam(tenant)) redirect("/dashboard");
  const roles = unwrap(await api.GET("/roles", { params: scope }));

  return (
    <main className="enter mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/team" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("title")}
      </Link>
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold">{t("rolesTitle")}</h1>
        <p className="text-sm text-muted">{t("rolesSubtitle")}</p>
      </div>
      {roles.custom.map((role) => (
        <RoleForm key={`${role.id}-${role.permissions.join()}-${role.name}`} role={role} permissions={roles.permissions} grantable={tenant.permissions} />
      ))}
      <section aria-labelledby="new-role-heading" className="flex flex-col gap-3">
        <h2 id="new-role-heading" className="text-lg font-semibold">
          {t("newRole")}
        </h2>
        <RoleForm permissions={roles.permissions} grantable={tenant.permissions} />
      </section>
    </main>
  );
}
