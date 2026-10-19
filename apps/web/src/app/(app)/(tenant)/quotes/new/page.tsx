import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { BackLink } from "@/components/back-link";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { getTenantFor } from "@/lib/tenant";

import { NewQuoteBody } from "./new-quote-body";

/** A new quote; `?client=` picks the client (from the client's card). */
export default async function NewQuotePage({ searchParams }: PageProps<"/quotes/new">) {
  const t = await getTranslations("quotes");
  await getTenantFor("sales.manage");
  const { client, example } = await searchParams;

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/quotes" label={t("back")} />
      <PageHeader title={t("new")} />
      <NewQuoteBody client={client} example={example === "1"} />
    </Container>
  );
}
