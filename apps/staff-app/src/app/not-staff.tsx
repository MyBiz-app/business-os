import { router } from "expo-router";
import { Text } from "react-native";
import { useTranslations } from "use-intl";

import { Button, Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { supabase } from "@business-os/app-kit/lib/supabase";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

export default function NotStaff() {
  const t = useTranslations("staffApp.notStaff");
  const { palette } = useTheme();
  return (
    <Screen palette={palette}>
      <Heading palette={palette}>{t("title")}</Heading>
      <Card palette={palette}>
        <Text style={[styles.muted, { color: palette.muted }]}>{t("text")}</Text>
      </Card>
      <Button
        label={t("signOut")}
        variant="secondary"
        palette={palette}
        onPress={() => {
          void supabase.auth.signOut().then(() => router.replace("/sign-in"));
        }}
      />
    </Screen>
  );
}
