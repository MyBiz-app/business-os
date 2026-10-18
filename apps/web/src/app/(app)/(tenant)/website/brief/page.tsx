import { getTranslations } from "next-intl/server";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { BackLink } from "@/components/back-link";

import { WizardBody } from "./wizard-body";

export default async function WebsiteBriefPage() {
  const t = await getTranslations("website");
  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/website" label={t("title")} />
      <PageHeader title={t("wizardTitle")} />
      <section className="card p-6">
        <WizardBody />
      </section>
    </Container>
  );
}
