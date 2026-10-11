import { router } from "expo-router";
import { Text } from "react-native";
import { useTranslations } from "use-intl";

import { ProfileForm } from "@/components/profile-form";
import { Badge, ListRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { SegmentedControl } from "@business-os/app-kit/components/segmented-control";
import { Button, Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { PreferencesCard } from "@business-os/app-kit/components/preferences-card";
import { useAccount } from "@/lib/use-account";
import { useHealth } from "@/lib/use-health";
import { useBusiness } from "@/providers/business-provider";
import { useSession } from "@business-os/app-kit/providers/session-provider";

export default function Profile() {
  const t = useTranslations();
  const { session } = useSession();
  const { businesses, business, select, palette } = useBusiness();
  // Quotes and bills (#44, #45), documents (#45) and addresses for on-site services (#42).
  const account = useAccount();
  const health = useHealth();
  const hasBills = account.quotes.some((q) => q.kind === "bill");
  const quotesTitle = hasBills ? t("client.profile.quotesAndBills") : t("quotes.title");
  const quotesBadge =
    account.toPay.length > 0
      ? { label: t("client.profile.toPay"), tone: "primary" as const }
      : account.toAnswer.length > 0
        ? { label: t("client.profile.toAnswer"), tone: "primary" as const }
        : null;
  const healthTone = health?.state === "ok" ? "success" : health?.state === "needs_review" ? "muted" : "danger";
  const hasAccountRows =
    account.documents.length > 0 || account.quotes.length > 0 || account.receipts > 0 || account.onSite || !!business?.dependents || !!health?.form;

  return (
    <Screen palette={palette}>
      <Heading palette={palette}>{t("client.profile.title")}</Heading>
      <Card palette={palette}>
        <Text style={[styles.h2, { color: palette.foreground }]}>
          {[business?.first_name, business?.last_name].filter(Boolean).join(" ")}
        </Text>
        <Text style={[styles.muted, { color: palette.muted }]}>
          {t("client.profile.signedInAs", { email: session?.user.email ?? "" })}
        </Text>
      </Card>

      {hasAccountRows && <SectionTitle title={t("client.profile.account")} palette={palette} />}
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
          title={quotesTitle}
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
      {business?.dependents && (
        <ListRow
          palette={palette}
          title={t(`dependents.mine.${business.dependents}`)}
          subtitle={t(`dependents.mineHint.${business.dependents}`)}
          onPress={() => router.push("/dependents")}
        />
      )}
      {health?.form && (
        <ListRow
          palette={palette}
          title={t("client.health.title")}
          subtitle={t(`health.states.${health.state}`)}
          trailing={
            health.state === "ok" ? null : (
              <Badge label={t(health.state === "expiring" ? "client.health.update" : "client.health.fill")} tone={healthTone} palette={palette} />
            )
          }
          onPress={() => router.push("/health")}
        />
      )}

      <ProfileForm key={business?.client_id} />

      {businesses && businesses.length > 1 && (
        <SegmentedControl
          label={t("client.profile.business")}
          options={businesses.map((b) => ({ value: b.id, label: b.name }))}
          value={business?.id ?? ""}
          onChange={(id) => void select(id)}
        />
      )}
      <Button label={t("client.profile.joinAnother")} variant="secondary" palette={palette} onPress={() => router.push("/join")} />

      <PreferencesCard palette={palette} signOutVariant="danger" />
    </Screen>
  );
}
