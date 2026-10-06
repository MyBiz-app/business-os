import { router } from "expo-router";
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
  const { businesses, business, select, palette } = useBusiness();
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
