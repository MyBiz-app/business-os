import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { unwrap } from "@/lib/api";
import { isolate } from "@/lib/bidi";
import { canManagePayroll } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { PayrollFile } from "./payroll-file";

export default async function PayrollFilePage({ params }: PageProps<"/team/[userId]/payroll">) {
  const { userId } = await params;
  const t = await getTranslations("payroll");
  const common = await getTranslations("common");
  const { api, scope, tenant } = await getTenantFor("payroll.read");
  const team = unwrap(await api.GET("/staff", { params: scope }));
  const member = team.members.find((m) => m.user_id === userId);
  if (!member) notFound();
  const path = { ...scope, path: { user_id: userId } };
  const [employment, forms, components] = await Promise.all([
    api.GET("/staff/{user_id}/employment", { params: path }).then(unwrap),
    api.GET("/staff/{user_id}/form101", { params: path }).then(unwrap),
    api.GET("/staff/{user_id}/pay-components", { params: path }).then(unwrap),
  ]);
  const name = member.full_name ?? member.email;

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <Link href="/team" className="text-sm text-primary-ink underline-offset-4 hover:underline">
        {common("back")}
      </Link>
      <PageHeader
        title={t("title", { name: isolate(name) })}
        description={[member.job_title, t("subtitle")].filter(Boolean).join(" · ")}
      />
      <PayrollFile
        userId={userId}
        name={name}
        currency={tenant.currency}
        locale={tenant.locale}
        employment={employment}
        forms={forms}
        components={components}
        canManage={canManagePayroll(tenant)}
        thisYear={new Date().getFullYear()}
      />
    </Container>
  );
}
