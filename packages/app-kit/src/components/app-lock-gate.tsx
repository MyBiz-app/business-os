import { useCallback, useEffect, useRef, useState } from "react";
import { AppState, StyleSheet, View } from "react-native";
import { useTranslations } from "use-intl";

import { authenticate, loadAppLock, shouldLock } from "../lib/app-lock";
import { supabase } from "../lib/supabase";
import { useSession } from "../providers/session-provider";
import { useTheme } from "../providers/theme-provider";
import { Text } from "./text";
import { Button, Heading, Screen, styles } from "./ui";

/** Covers the app with a Face ID / fingerprint prompt when the user turned the lock on in their
 * preferences: at launch, and after the app has been in the background for a while. The session
 * itself stays in the phone's secure store; this only guards the screen. */
export function AppLockGate({ children }: { children: React.ReactNode }) {
  const t = useTranslations("appLock");
  const { palette } = useTheme();
  const { session } = useSession();
  const [locked, setLocked] = useState<boolean | null>(null);
  const [failed, setFailed] = useState(false);
  const enabled = useRef(false);
  const backgroundedAt = useRef<number | null>(null);
  const prompting = useRef(false);

  const unlock = useCallback(async () => {
    if (prompting.current) return;
    prompting.current = true;
    setFailed(false);
    const ok = await authenticate(t("prompt"), t("cancel"));
    prompting.current = false;
    if (ok) setLocked(false);
    else setFailed(true);
  }, [t]);

  // At launch: read the preference once.
  useEffect(() => {
    void loadAppLock().then((on) => {
      enabled.current = on;
      setLocked(on);
    });
  }, []);

  // The preference can change while the app runs (the toggle in "me").
  useEffect(() => {
    const timer = setInterval(() => void loadAppLock().then((on) => (enabled.current = on)), 3000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      // The biometric prompt itself briefly leaves the foreground; ignore that.
      if (prompting.current) return;
      if (state === "background") backgroundedAt.current = Date.now();
      else if (state === "active") {
        if (shouldLock(enabled.current, backgroundedAt.current, Date.now())) setLocked(true);
        backgroundedAt.current = null;
      }
    });
    return () => subscription.remove();
  }, []);

  const showLock = locked === true && !!session;
  useEffect(() => {
    if (showLock) void unlock();
  }, [showLock, unlock]);

  // Hide the app until we know whether it is locked, so nothing flashes first.
  if (locked === null) return null;

  // The app stays mounted underneath, so unlocking returns to the same screen.
  return (
    <>
      {children}
      {showLock ? (
        <View style={[StyleSheet.absoluteFill, { backgroundColor: palette.background }]}>
          <Screen palette={palette}>
            <View style={{ flex: 1, justifyContent: "center", gap: 16 }}>
              <Heading palette={palette}>{t("title")}</Heading>
              <Text style={[styles.muted, { color: palette.muted }]}>{failed ? t("failed") : t("subtitle")}</Text>
              <Button label={t("unlock")} palette={palette} onPress={() => void unlock()} />
              <Button
                label={t("signOut")}
                variant="secondary"
                palette={palette}
                onPress={() => {
                  setLocked(false);
                  void supabase.auth.signOut();
                }}
              />
            </View>
          </Screen>
        </View>
      ) : null}
    </>
  );
}
