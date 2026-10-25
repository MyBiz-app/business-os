import { router } from "expo-router";
import { Text } from "@business-os/app-kit/components/text";
import { useTranslations } from "use-intl";

import { AreaSwitcher } from "@/components/area-switcher";
import { ProfileHeader } from "@/components/profile-header";
import { CancellationPolicyCard } from "@/components/cancellation-policy-card";
import { ClientIdentityCard } from "@/components/identity-card";
import { MarketingConsentCard } from "@/components/marketing-consent";
import { ProfileForm } from "@/components/profile-form";
import { Badge, ListRow, RowGroup, SectionTitle } from "@business-os/app-kit/components/rows";
import { SegmentedControl } from "@business-os/app-kit/components/segmented-control";
import { Button, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { PreferencesCard } from "@business-os/app-kit/components/preferences-card";
import { BusinessInfo } from "@/components/home-cards";
import { useLocations } from "@/lib/use-locations";
import { useFriendSettings } from "@/lib/use-friend-settings";
import { useHealth } from "@/lib/use-health";
import { useBusiness } from "@/providers/business-provider";
import { useSession } from "@business-os/app-kit/providers/session-provider";

export default function Profile() {
  const t = useTranslations();
  const { session } = useSession();
  const { businesses, business, select, palette } = useBusiness();
  const health = useHealth();
  const friends = useFriendSettings().data;
  const healthTone = health?.state === "ok" ? "success" : health?.state === "needs_review" ? "muted" : "danger";
  const hasAccountRows = !!business?.dependents || !!health?.form;
  const locations = useLocations();

  return (
    <Screen title={t("client.profile.title")} palette={palette}>
      <ProfileHeader name={[business?.first_name, business?.last_name].filter(Boolean).join(" ")} />
      <Text style={[styles.muted, { color: palette.muted }]}>
        {t("client.profile.signedInAs", { email: session?.user.email ?? "" })}
      </Text>

      {friends?.enabled && (
        <ListRow
          palette={palette}
          title={t("friends.title")}
          subtitle={t("friends.hint")}
          onPress={() => router.push("/friends")}
        />
      )}

      {hasAccountRows && <SectionTitle title={t("client.profile.myDetails")} palette={palette} />}
      <RowGroup palette={palette}>
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
      </RowGroup>

      <BusinessInfo data={{ locations }} />

      <ProfileForm key={business?.client_id} />
      <ClientIdentityCard key={`id-${business?.client_id}`} />
      {business && <CancellationPolicyCard key={`policy-${business.id}`} palette={palette} tenantId={business.id} />}
      <MarketingConsentCard palette={palette} />

      {businesses && businesses.length > 1 && (
        <SegmentedControl
          label={t("client.profile.business")}
          options={businesses.map((b) => ({ value: b.id, label: b.name }))}
          value={business?.id ?? ""}
          onChange={(id) => void select(id)}
        />
      )}
      <AreaSwitcher palette={palette} />
      <Button label={t("client.profile.joinAnother")} variant="secondary" palette={palette} onPress={() => router.push("/join")} />

      <PreferencesCard palette={palette} signOutVariant="danger" />
    </Screen>
  );
}
