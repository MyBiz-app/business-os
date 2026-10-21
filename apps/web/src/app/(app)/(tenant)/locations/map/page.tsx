import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { BackLink } from "@/components/back-link";
import { BranchMap } from "@/components/branch-map/branch-map";
import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { loadBranchMap, loadClientCities } from "@/lib/branch-map";
import { getTenantFor } from "@/lib/tenant";

import { openBranch } from "../actions";

export default async function BranchMapPage({ searchParams }: PageProps<"/locations/map">) {
  const t = await getTranslations("branchMap");
  const tNav = await getTranslations("nav");
  const context = await getTenantFor("reports.read");
  const [branches, clientCities] = await Promise.all([loadBranchMap(context), loadClientCities(context)]);
  const { branch } = await searchParams;
  const initial = typeof branch === "string" && branches.some((b) => b.id === branch) ? branch : null;

  return (
    <Container as="main" size="wide" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/locations" label={tNav("locations")} />
      <PageHeader title={t("title")} description={t("subtitle")} />
      {branches.length === 0 ? (
        <EmptyState variant="list">
          {t("empty")}{" "}
          <Link href="/locations" className="text-primary-ink underline underline-offset-4 hover:no-underline">
            {t("emptyLink")}
          </Link>
        </EmptyState>
      ) : (
        <BranchMap branches={branches} currency={context.tenant.currency} initialBranch={initial} openBranch={openBranch} clientCities={clientCities} />
      )}
    </Container>
  );
}
