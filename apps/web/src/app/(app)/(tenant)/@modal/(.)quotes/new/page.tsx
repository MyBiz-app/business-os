import { getTranslations } from "next-intl/server";

import { RouteModal } from "@/components/ui/route-modal";
import { getTenantFor } from "@/lib/tenant";

import { NewQuoteBody } from "../../../quotes/new/new-quote-body";

export default async function NewQuoteModal({ searchParams }: PageProps<"/quotes/new">) {
  const t = await getTranslations("quotes");
  await getTenantFor("sales.manage");
  const { client, example } = await searchParams;
  return (
    <RouteModal title={t("new")} size="lg">
      <NewQuoteBody client={client} example={example === "1"} plain />
    </RouteModal>
  );
}
