import { useEffect, useState } from "react";
import { View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { SegmentedControl } from "@business-os/app-kit/components/segmented-control";
import { useToast } from "@business-os/app-kit/components/toast";
import { Card, styles } from "@business-os/app-kit/components/ui";
import { apiClient, unwrap } from "@business-os/app-kit/lib/api";
import type { Palette } from "@business-os/app-kit/lib/theme";
import { useTranslations } from "use-intl";

/** Whether the person agreed to marketing messages (offers and news). Service messages about
 * their bookings and account are sent either way; the backend only sends marketing to people
 * who said yes. Off until they choose. */
export function MarketingConsentCard({ palette }: { palette: Palette }) {
  const t = useTranslations("client.profile.marketing");
  const toast = useToast();
  const [consent, setConsent] = useState<boolean | null>(null);

  useEffect(() => {
    let live = true;
    apiClient()
      .GET("/me")
      .then(unwrap)
      .then((me) => live && setConsent(me.marketing_consent))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  if (consent === null) return null;

  const choose = async (next: boolean) => {
    const before = consent;
    setConsent(next);
    try {
      unwrap(await apiClient().PUT("/me/marketing-consent", { body: { consent: next, source: "app_profile" } }));
      toast("success", t(next ? "saidYes" : "saidNo"));
    } catch {
      setConsent(before);
      toast("error", t("failed"));
    }
  };

  return (
    <Card palette={palette}>
      <View style={{ gap: 12 }}>
        <SegmentedControl
          label={t("title")}
          value={consent ? "on" : "off"}
          options={[
            { value: "on", label: t("on") },
            { value: "off", label: t("off") },
          ]}
          onChange={(value) => void choose(value === "on")}
        />
        <Text style={[styles.muted, { color: palette.muted }]}>{t("hint")}</Text>
      </View>
    </Card>
  );
}
