import { locales } from "@business-os/i18n";
import { router } from "expo-router";
import { useTranslations } from "use-intl";

import { supabase } from "../lib/supabase";
import type { Palette } from "../lib/theme";
import type { ThemePreference } from "../lib/preferences";
import { useLocaleSetting } from "../providers/i18n-provider";
import { useTheme } from "../providers/theme-provider";
import { SegmentedControl } from "./segmented-control";
import { Button, Card } from "./ui";

const THEMES: ThemePreference[] = ["system", "light", "dark"];

/** Language, look and sign-out: the same card at the end of every app's "me" screen. */
export function PreferencesCard({ palette, signOutVariant = "secondary" }: { palette: Palette; signOutVariant?: "secondary" | "danger" }) {
  const t = useTranslations("business.me");
  const tLocales = useTranslations("locales");
  const { preference, setPreference } = useTheme();
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
        <SegmentedControl
          label={t("theme")}
          value={preference}
          options={THEMES.map((value) => ({ value, label: t(`themes.${value}`) }))}
          onChange={setPreference}
        />
      </Card>
      <Button
        label={t("signOut")}
        variant={signOutVariant}
        palette={palette}
        onPress={() => void supabase.auth.signOut().then(() => router.replace("/sign-in"))}
      />
    </>
  );
}
