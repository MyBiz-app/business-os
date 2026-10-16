import { useTranslations } from "use-intl";

import { PreferencesCard } from "@business-os/app-kit/components/preferences-card";
import { Text } from "@business-os/app-kit/components/text";
import { Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";
import { AreaSwitcher } from "@/components/area-switcher";

/** Shown when the account is not (or no longer) on the MyBiz team; other areas stay reachable. */
export default function NotTeam() {
  const t = useTranslations("staffApp.notStaff");
  const { palette } = useTheme();
  return (
    <Screen palette={palette}>
      <Heading palette={palette}>{t("title")}</Heading>
      <Card palette={palette}>
        <Text style={[styles.muted, { color: palette.muted }]}>{t("text")}</Text>
      </Card>
      <AreaSwitcher palette={palette} />
      <PreferencesCard palette={palette} signOutVariant="danger" />
    </Screen>
  );
}
