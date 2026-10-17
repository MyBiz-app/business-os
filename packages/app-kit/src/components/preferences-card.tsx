import { locales } from "@business-os/i18n";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Alert, View } from "react-native";
import { useTranslations } from "use-intl";

import { authenticate, isAppLockSupported, loadAppLock, loadLockTimeout, LOCK_TIMEOUTS, saveAppLock, saveLockTimeout, type LockTimeout } from "../lib/app-lock";
import { ApiError, apiClient } from "../lib/api";
import { confirm } from "../lib/confirm";
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
  const tLock = useTranslations("appLock");
  const [lockSupported, setLockSupported] = useState(false);
  const [lockOn, setLockOn] = useState(false);
  const [lockTimeout, setLockTimeout] = useState<LockTimeout>("30s");
  useEffect(() => {
    void loadLockTimeout().then(setLockTimeout);
    void isAppLockSupported().then(setLockSupported);
    void loadAppLock().then(setLockOn);
  }, []);
  // Turning the lock on first proves the phone can verify the user, so they can never lock themselves out.
  const changeLock = async (on: boolean) => {
    if (on && !(await authenticate(tLock("prompt"), tLock("cancel")))) return;
    await saveAppLock(on);
    setLockOn(on);
  };

  const tDelete = useTranslations("accountDeletion");
  // Store rule (Apple and Google): an account made in the app can be deleted in the app.
  const deleteAccount = async () => {
    if (!(await confirm(tDelete("confirmTitle"), tDelete("confirmBody"), tDelete("yes"), tDelete("no")))) return;
    try {
      const result = await apiClient().DELETE("/me", { body: { confirm: true } });
      if (result.error !== undefined) {
        throw new ApiError(result.response.status, (result.error as { detail?: string }).detail);
      }
    } catch (error) {
      Alert.alert(tDelete(error instanceof ApiError && error.detail === "owns_business" ? "ownsBusiness" : "failed"));
      return;
    }
    await unregisterPushToken().catch(() => undefined);
    await saveAppLock(false);
    await supabase.auth.signOut();
    router.replace("/sign-in");
  };

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
        {lockSupported ? (
          <SegmentedControl
            label={tLock("setting")}
            value={lockOn ? "on" : "off"}
            options={[
              { value: "off", label: tLock("off") },
              { value: "on", label: tLock("on") },
            ]}
            onChange={(value) => void changeLock(value === "on")}
          />
        ) : null}
        {lockSupported && lockOn ? (
          <SegmentedControl
            label={tLock("timeout")}
            value={lockTimeout}
            options={LOCK_TIMEOUTS.map((value) => ({ value, label: tLock(`timeouts.${value}`) }))}
            onChange={(value) => {
              setLockTimeout(value);
              void saveLockTimeout(value);
            }}
          />
        ) : null}
      </Card>
      <Button
        label={t("signOut")}
        variant={signOutVariant}
        palette={palette}
        onPress={() =>
          void unregisterPushToken()
            .then(() => saveAppLock(false))
            .then(() => supabase.auth.signOut())
            .then(() => router.replace("/sign-in"))
        }
      />
      <Button label={tDelete("button")} variant="secondary" palette={palette} onPress={() => void deleteAccount()} />
    </>
  );
}
