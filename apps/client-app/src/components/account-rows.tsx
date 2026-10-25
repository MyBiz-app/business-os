import { router } from "expo-router";
import { useTranslations } from "use-intl";

import { Badge, ListRow, RowGroup, SectionTitle } from "@business-os/app-kit/components/rows";
import { useAccount } from "@/lib/use-account";
import { useBusiness } from "@/providers/business-provider";

/** What the client keeps with this business: documents, quotes and bills, receipts and addresses.
 * Lives in the Mine tab; draws nothing when there is none of it. */
export function AccountRows() {
  const t = useTranslations();
  const { palette } = useBusiness();
  const account = useAccount();
  const hasBills = account.quotes.some((q) => q.kind === "bill");
  const quotesBadge =
    account.toPay.length > 0
      ? { label: t("client.profile.toPay"), tone: "primary" as const }
      : account.toAnswer.length > 0
        ? { label: t("client.profile.toAnswer"), tone: "primary" as const }
        : null;
  if (account.documents.length + account.quotes.length === 0 && account.receipts === 0 && !account.onSite) return null;

  return (
    <>
      <SectionTitle title={t("client.profile.account")} palette={palette} />
      <RowGroup palette={palette}>
        {account.documents.length > 0 && (
          <ListRow
            palette={palette}
            title={t("documents.mine")}
            subtitle={t("documents.mineHint")}
            trailing={
              account.toSign.length > 0 ? (
                <Badge label={t("client.profile.toSign", { count: account.toSign.length })} tone="danger" palette={palette} />
              ) : null
            }
            onPress={() => router.push("/documents")}
          />
        )}
        {account.quotes.length > 0 && (
          <ListRow
            palette={palette}
            title={hasBills ? t("client.profile.quotesAndBills") : t("quotes.title")}
            trailing={quotesBadge ? <Badge label={quotesBadge.label} tone={quotesBadge.tone} palette={palette} /> : null}
            onPress={() => router.push("/quotes")}
          />
        )}
        {account.receipts > 0 && (
          <ListRow
            palette={palette}
            title={t("client.profile.receipts")}
            subtitle={t("client.profile.receiptsHint")}
            onPress={() => router.push("/receipts")}
          />
        )}
        {account.onSite && (
          <ListRow
            palette={palette}
            title={t("jobs.myAddresses")}
            subtitle={t("jobs.myAddressesHint")}
            onPress={() => router.push("/addresses")}
          />
        )}
      </RowGroup>
    </>
  );
}
