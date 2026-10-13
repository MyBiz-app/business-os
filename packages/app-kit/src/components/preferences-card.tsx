import { locales } from "@business-os/i18n";
import { router } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { unregisterPushToken } from "../lib/push";
import { supabase } from "../lib/supabase";
import type { Palette } from "../lib/theme";
import type { TextSize, ThemePreference } from "../lib/preferences";
import { useLocaleSetting } from "../providers/i18n-provider";
import { useTheme } from "../providers/theme-provider";
import { SegmentedControl } from "./segmented-control";
import { ThemeToggle } from "./theme-toggle";
import { Button, Card } from "./ui";

const TEXT_SIZES: TextSize[] = ["normal", "large", "larger"];
const THEMES: ThemePreference[] = ["system", "light", "dark"];

/** Language, look and sign-out: the same card at the end of every app's "me" screen. */
export function PreferencesCard({ palette, signOutVariant = "secondary" }: { palette: Palette; signOutVariant?: "secondary" | "danger" }) {
  const t = useTranslations("business.me");
  const tLocales = useTranslations("locales");
  const { preference, setPreference, highContrast, setHighContrast, textSize, setTextSize, reduceMotion, setReduceMotion } = useTheme();
  const { locale, setLocale } = useLocaleSetting();

  return (
    <>
      <Card palette={palette}>
        <SegmentedControl
          label={t("language")}
          value={locale}
          options={locales.map((value) => ({ value, label: tLocales(value) }))}
          onChange={(value) => void setLocale(value)}
        />
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <View style={{ flex: 1 }}>
            <SegmentedControl
              label={t("theme")}
              value={preference}
              options={THEMES.map((value) => ({ value, label: t(`themes.${value}`) }))}
              onChange={setPreference}
            />
          </View>
          <ThemeToggle />
        </View>
        <SegmentedControl
          label={t("contrast")}
          value={highContrast ? "high" : "normal"}
          options={[
            { value: "normal", label: t("contrastNormal") },
            { value: "high", label: t("contrastHigh") },
          ]}
          onChange={(value) => setHighContrast(value === "high")}
        />
        <SegmentedControl
          label={t("textSize")}
          value={textSize}
          options={TEXT_SIZES.map((value) => ({ value, label: t(`textSizes.${value}`) }))}
          onChange={setTextSize}
        />
        <SegmentedControl
          label={t("motion")}
          value={reduceMotion ? "reduced" : "normal"}
          options={[
            { value: "normal", label: t("motionNormal") },
            { value: "reduced", label: t("motionReduced") },
          ]}
          onChange={(value) => setReduceMotion(value === "reduced")}
        />
      </Card>
      <Button
        label={t("signOut")}
        variant={signOutVariant}
        palette={palette}
        onPress={() =>
          void unregisterPushToken()
            .then(() => supabase.auth.signOut())
            .then(() => router.replace("/sign-in"))
        }
      />
    </>
  );
}
