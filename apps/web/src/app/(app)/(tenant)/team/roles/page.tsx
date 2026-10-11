import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { redirect } from "next/navigation";

import { PermissionList } from "@/components/permission-list";
import { unwrap } from "@/lib/api";
import { canManageTeam } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { RoleForm } from "./role-form";

export default async function RolesPage() {
  const t = await getTranslations("team");
  const tRoles = await getTranslations("roles");
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
      <section aria-labelledby="system-roles-heading" className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <h2 id="system-roles-heading" className="text-lg font-semibold">
            {t("systemRolesTitle")}
          </h2>
          <p className="text-sm text-muted">{t("systemRolesHint")}</p>
        </div>
        {roles.system.map((role) => (
          <details key={role.key} className="card group p-5">
            <summary className="cursor-pointer list-none font-medium [&::-webkit-details-marker]:hidden">{tRoles(role.key)}</summary>
            <div className="mt-3">
              <PermissionList all={roles.permissions} allowed={role.permissions} />
            </div>
          </details>
        ))}
      </section>
      <section aria-labelledby="custom-roles-heading" className="flex flex-col gap-3">
        <h2 id="custom-roles-heading" className="text-lg font-semibold">
          {t("customRolesTitle")}
        </h2>
        {roles.custom.length === 0 && <p className="text-sm text-muted">{t("noCustomRoles")}</p>}
        {roles.custom.map((role) => (
          <RoleForm key={`${role.id}-${role.permissions.join()}-${role.name}`} role={role} permissions={roles.permissions} grantable={tenant.permissions} />
        ))}
      </section>
      <section aria-labelledby="new-role-heading" className="flex flex-col gap-3">
        <h2 id="new-role-heading" className="text-lg font-semibold">
          {t("newRole")}
        </h2>
        <RoleForm permissions={roles.permissions} grantable={tenant.permissions} />
      </section>
    </main>
  );
}
