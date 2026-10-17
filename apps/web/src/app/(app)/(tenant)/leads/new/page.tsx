import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

import { NewLeadBody } from "./new-lead-body";

export default async function NewLeadPage() {
  const t = await getTranslations("leads");
  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <Link href="/leads" className="text-sm text-primary-ink underline-offset-4 hover:underline">
        {t("back")}
      </Link>
      <PageHeader title={t("new")} />
      <section className="card p-6">
        <NewLeadBody />
      </section>
    </Container>
  );
}
