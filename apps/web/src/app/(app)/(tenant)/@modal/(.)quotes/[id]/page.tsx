import { getTranslations } from "next-intl/server";

import { RouteModal } from "@/components/ui/route-modal";

import { loadQuote, QuoteBody } from "../../../quotes/[id]/quote-body";

export default async function QuoteModal({ params }: PageProps<"/quotes/[id]">) {
  const { id } = await params;
  const t = await getTranslations("quotes");
  const { quote } = await loadQuote(id);
  return (
    <RouteModal title={`#${quote.number} ${quote.title}`} description={`${quote.client_name} · ${t(`statuses.${quote.status}`)}`} size="lg">
      <QuoteBody id={id} />
    </RouteModal>
  );
}
