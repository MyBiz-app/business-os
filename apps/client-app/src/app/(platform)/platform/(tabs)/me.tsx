import { Text } from "@business-os/app-kit/components/text";
import { useTranslations } from "use-intl";

import { Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { PreferencesCard } from "@business-os/app-kit/components/preferences-card";
import { AreaSwitcher } from "@/components/area-switcher";
import { useSession } from "@business-os/app-kit/providers/session-provider";
import { usePlatform } from "@/providers/platform-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";


/** The team member's own settings and what their level allows. */
export default function Me() {
  const t = useTranslations("staffApp.me");
  const tLevels = useTranslations("platform.levels");
  const tPermissions = useTranslations("platform.permissions");
  const { staff } = usePlatform();
  const { session } = useSession();
  const { palette } = useTheme();

  return (
    <Screen palette={palette}>
      <Heading palette={palette}>{t("title")}</Heading>
      <Card palette={palette}>
        <Text style={[styles.muted, { color: palette.muted, writingDirection: "ltr" }]}>{session?.user.email}</Text>
        {staff && <Text style={{ color: palette.foreground, fontWeight: "600" }}>{t("level", { level: tLevels(staff.level) })}</Text>}
      </Card>

      {staff && staff.permissions.length > 0 && (
        <Card palette={palette}>
          <Text style={{ color: palette.foreground, fontWeight: "600" }}>{t("permissions")}</Text>
          {staff.permissions.map((permission) => (
            <Text key={permission} style={[styles.muted, { color: palette.muted }]}>
              {tPermissions(`${permission.replace(".", "_") as "businesses_read"}.name`)}
            </Text>
          ))}
        </Card>
      )}

      <AreaSwitcher palette={palette} />
      <PreferencesCard palette={palette} />
    </Screen>
  );
}
