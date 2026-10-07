import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Text } from "react-native";
import { useTranslations } from "use-intl";

import { ProfileForm } from "@/components/profile-form";
import { SegmentedControl } from "@business-os/app-kit/components/segmented-control";
import { Button, Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { PreferencesCard } from "@business-os/app-kit/components/preferences-card";
import { useHealth } from "@/lib/use-health";
import { useBusiness } from "@/providers/business-provider";
import { useSession } from "@business-os/app-kit/providers/session-provider";

export default function Profile() {
  const t = useTranslations();
  const { session } = useSession();
  const { businesses, business, select, palette, api, scope } = useBusiness();
  // On-site services (#42) happen at the client's addresses.
  const [onSite, setOnSite] = useState(false);
  const [hasQuotes, setHasQuotes] = useState(false);
  const [hasDocuments, setHasDocuments] = useState(false);
  useEffect(() => {
    if (!business) return;
    let active = true;
    void api
      .GET("/client/appointments/services", { params: scope })
      .then((r) => active && setOnSite((r.data ?? []).some((s) => s.on_site)))
      .catch(() => undefined);
    // Quotes the business sent me (#44).
    void api
      .GET("/client/quotes", { params: scope })
      .then((r) => active && setHasQuotes((r.data ?? []).length > 0))
      .catch(() => undefined);
    // Documents the business shared with me (#45).
    void api
      .GET("/client/documents", { params: scope })
      .then((r) => active && setHasDocuments((r.data ?? []).length > 0))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [api, scope, business]);
  const health = useHealth();

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

      <ProfileForm key={business?.client_id} />

      {hasDocuments && (
        <Card palette={palette}>
          <Text style={[styles.h2, { color: palette.foreground }]}>{t("documents.mine")}</Text>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("documents.mineHint")}</Text>
          <Button label={t("documents.mine")} variant="secondary" palette={palette} onPress={() => router.push("/documents")} />
        </Card>
      )}

      {hasQuotes && (
        <Card palette={palette}>
          <Text style={[styles.h2, { color: palette.foreground }]}>{t("quotes.title")}</Text>
          <Button label={t("quotes.title")} variant="secondary" palette={palette} onPress={() => router.push("/quotes")} />
        </Card>
      )}

      {onSite && (
        <Card palette={palette}>
          <Text style={[styles.h2, { color: palette.foreground }]}>{t("jobs.myAddresses")}</Text>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("jobs.myAddressesHint")}</Text>
          <Button label={t("jobs.myAddresses")} variant="secondary" palette={palette} onPress={() => router.push("/addresses")} />
        </Card>
      )}

      {business?.dependents && (
        <Card palette={palette}>
          <Text style={[styles.h2, { color: palette.foreground }]}>{t(`dependents.mine.${business.dependents}`)}</Text>
          <Text style={[styles.muted, { color: palette.muted }]}>{t(`dependents.mineHint.${business.dependents}`)}</Text>
          <Button
            label={t(`dependents.mine.${business.dependents}`)}
            variant="secondary"
            palette={palette}
            onPress={() => router.push("/dependents")}
          />
        </Card>
      )}

      {health?.form && (
        <Card palette={palette}>
          <Text style={[styles.h2, { color: palette.foreground }]}>{t("client.health.title")}</Text>
          <Text style={[styles.muted, { color: palette.muted }]}>{t(`health.states.${health.state}`)}</Text>
          <Button
            label={
              health.state === "ok"
                ? t("client.health.view")
                : health.state === "expiring"
                  ? t("client.health.update")
                  : t("client.health.fill")
            }
            variant={health.state === "ok" ? "secondary" : "primary"}
            palette={palette}
            onPress={() => router.push("/health")}
          />
        </Card>
      )}

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
