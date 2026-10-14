import { useTranslations } from "use-intl";

import { Text } from "@business-os/app-kit/components/text";
import { Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { PreferencesCard } from "@business-os/app-kit/components/preferences-card";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";
import { AreaSwitcher } from "@/components/area-switcher";
import { useAreas } from "@/providers/area-provider";

/** Stand-in for an area whose screens have not moved into this app yet (R5/R6). */
export function AreaPlaceholder({ kind }: { kind: "business" | "platform" }) {
  const t = useTranslations("areas");
  const { palette } = useTheme();
  const { active } = useAreas();
  return (
    <Screen palette={palette}>
      <Heading palette={palette}>{active?.name ?? ""}</Heading>
      <Card palette={palette}>
        <Text style={[styles.muted, { color: palette.muted }]}>{t(`soon.${kind}`)}</Text>
      </Card>
      <AreaSwitcher palette={palette} />
      <PreferencesCard palette={palette} signOutVariant="danger" />
    </Screen>
  );
}
