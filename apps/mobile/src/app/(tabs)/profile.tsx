import { locales } from "@business-os/i18n";
import { router } from "expo-router";
import { Text, View } from "react-native";
import { useTranslations } from "use-intl";

import { SegmentedControl } from "@/components/segmented-control";
import { Button, Card, Heading, Screen, styles } from "@/components/ui";
import type { ThemePreference } from "@/lib/preferences";
import { supabase } from "@/lib/supabase";
import { useBusiness } from "@/providers/business-provider";
import { useLocaleSetting } from "@/providers/i18n-provider";
import { useSession } from "@/providers/session-provider";
import { useTheme } from "@/providers/theme-provider";

export default function Profile() {
  const t = useTranslations();
  const { session } = useSession();
  const { businesses, business, select, palette } = useBusiness();
  const { preference, setPreference } = useTheme();
  const { locale, setLocale } = useLocaleSetting();

  const themeOptions: { value: ThemePreference; label: string }[] = [
    { value: "light", label: t("settings.themeLight") },
    { value: "dark", label: t("settings.themeDark") },
    { value: "system", label: t("settings.themeSystem") },
  ];

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

      {businesses && businesses.length > 1 && (
        <SegmentedControl
          label={t("client.profile.business")}
          options={businesses.map((b) => ({ value: b.id, label: b.name }))}
          value={business?.id ?? ""}
          onChange={(id) => void select(id)}
        />
      )}
      <Button label={t("client.profile.joinAnother")} variant="secondary" palette={palette} onPress={() => router.push("/join")} />

      <SegmentedControl
        label={t("settings.language")}
        options={locales.map((value) => ({ value, label: t(`locales.${value}`) }))}
        value={locale}
        onChange={(value) => void setLocale(value)}
      />
      <SegmentedControl label={t("settings.theme")} options={themeOptions} value={preference} onChange={setPreference} />

      <View style={{ marginTop: 12 }}>
        <Button
          label={t("client.profile.signOut")}
          variant="danger"
          palette={palette}
          onPress={() => void supabase.auth.signOut().then(() => router.replace("/sign-in"))}
        />
      </View>
    </Screen>
  );
}
