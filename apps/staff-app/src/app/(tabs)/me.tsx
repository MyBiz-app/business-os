import { locales } from "@business-os/i18n";
import { router } from "expo-router";
import { Text } from "react-native";
import { useTranslations } from "use-intl";

import { SegmentedControl } from "@business-os/app-kit/components/segmented-control";
import { Button, Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { supabase } from "@business-os/app-kit/lib/supabase";
import { useLocaleSetting } from "@business-os/app-kit/providers/i18n-provider";
import { useSession } from "@business-os/app-kit/providers/session-provider";
import { useStaff } from "@/providers/staff-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

const THEMES = ["system", "light", "dark"] as const;

/** The team member's own settings and what their level allows. */
export default function Me() {
  const t = useTranslations("staffApp.me");
  const tBusiness = useTranslations("business.me");
  const tLevels = useTranslations("platform.levels");
  const tPermissions = useTranslations("platform.permissions");
  const { staff } = useStaff();
  const { session } = useSession();
  const { palette, preference, setPreference } = useTheme();
  const { locale, setLocale } = useLocaleSetting();

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

      <Card palette={palette}>
        <SegmentedControl
          label={tBusiness("language")}
          value={locale}
          options={locales.map((value) => ({ value, label: value === "he" ? "עברית" : "English" }))}
          onChange={(value) => void setLocale(value as "he")}
        />
        <SegmentedControl
          label={tBusiness("theme")}
          value={preference}
          options={THEMES.map((value) => ({ value, label: tBusiness(`themes.${value}`) }))}
          onChange={(value) => setPreference(value as "system")}
        />
      </Card>

      <Button
        label={tBusiness("signOut")}
        variant="secondary"
        palette={palette}
        onPress={() => {
          void supabase.auth.signOut().then(() => router.replace("/sign-in"));
        }}
      />
    </Screen>
  );
}
