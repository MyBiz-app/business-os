import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { HoursForm } from "@/components/form/hours-form";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { unwrap } from "@/lib/api";
import { isolate } from "@/lib/bidi";
import { toBlocks, weekStartFor } from "@/lib/hours";
import { getTenantFor } from "@/lib/tenant";

import { saveAvailability } from "./actions";

/** A manager sets the hours of the week a team member can work shifts (the shift board warns
 * when a shift falls outside them). Only people the manager can see in the team list. */
export default async function StaffAvailabilityPage({ params }: PageProps<"/team/[userId]/availability">) {
  const { userId } = await params;
  const t = await getTranslations();
  const { api, scope, tenant } = await getTenantFor("staff.manage");
  const team = unwrap(await api.GET("/staff", { params: scope }));
  const member = team.members.find((m) => m.user_id === userId);
  if (!member) notFound();
  const availability = unwrap(await api.GET("/staff/{user_id}/availability", { params: { ...scope, path: { user_id: userId } } }));

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <Link href="/team" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("common.back")}
      </Link>
      <PageHeader title={t("availability.title")} description={t("availability.subtitle", { name: isolate(member.full_name ?? member.email) })} />
      <section className="card flex flex-col gap-4 p-6">
        <p className="text-sm text-muted">{t("availability.hint")}</p>
        <HoursForm
          save={saveAvailability.bind(null, userId)}
          weekStartsOn={weekStartFor(tenant.locale)}
          initial={toBlocks(availability.windows)}
          emptyLabel={t("availability.none")}
          savedLabel={t("availability.saved")}
        />
      </section>
    </Container>
  );
}
