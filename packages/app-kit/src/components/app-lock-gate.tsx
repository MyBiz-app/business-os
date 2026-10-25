import { useCallback, useEffect, useRef, useState } from "react";
import { AppState, Modal, StyleSheet, View } from "react-native";
import { useTranslations } from "use-intl";

import Ionicons from "@expo/vector-icons/Ionicons";
import { authenticate, isAppLockDecided, isAppLockSupported, loadAppLock, loadLockTimeout, markLockOffered, saveAppLock, shouldLock, wasLockOffered, type LockTimeout } from "../lib/app-lock";
import { initialOf, shouldOfferLock } from "../lib/app-lock-rules";
import { tint } from "../lib/brand";
import { supabase } from "../lib/supabase";
import { useSession } from "../providers/session-provider";
import { useTheme } from "../providers/theme-provider";
import { AuthCard, AuthShell } from "./auth-shell";
import { DepthLogo } from "./launch-splash";
import { Text } from "./text";
import { Button, Heading, styles } from "./ui";
import { radius, scrimColor } from "../lib/theme";

/** Covers the app with a Face ID / fingerprint prompt when the user turned the lock on in their
 * preferences: at launch, and after the app has been in the background for a while. The session
 * itself stays in the phone's secure store; this only guards the screen. */
export function AppLockGate({ children }: { children: React.ReactNode }) {
  const t = useTranslations("appLock");
  const { palette, scheme } = useTheme();
  const { session } = useSession();
  const [locked, setLocked] = useState<boolean | null>(null);
  const [failed, setFailed] = useState(false);
  const enabled = useRef(false);
  const timeout = useRef<LockTimeout>("30s");
  const [offer, setOffer] = useState(false);
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
    void loadLockTimeout().then((value) => (timeout.current = value));
    void loadAppLock().then((on) => {
      enabled.current = on;
      setLocked(on);
    });
  }, []);

  // The preference can change while the app runs (the toggle in "me").
  useEffect(() => {
    const timer = setInterval(() => {
      void loadAppLock().then((on) => (enabled.current = on));
      void loadLockTimeout().then((value) => (timeout.current = value));
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      // The biometric prompt itself briefly leaves the foreground; ignore that.
      if (prompting.current) return;
      if (state === "background") backgroundedAt.current = Date.now();
      else if (state === "active") {
        if (shouldLock(enabled.current, backgroundedAt.current, Date.now(), timeout.current)) setLocked(true);
        backgroundedAt.current = null;
      }
    });
    return () => subscription.remove();
  }, []);

  const showLock = locked === true && !!session;
  const identity = session?.user.email ?? session?.user.phone ?? "";
  useEffect(() => {
    if (showLock) void unlock();
  }, [showLock, unlock]);

  // First sign-in on a phone that can check Face ID / a fingerprint: offer to use it next time (once).
  const signedIn = !!session;
  useEffect(() => {
    if (!signedIn || showLock) return;
    let live = true;
    void Promise.all([isAppLockSupported(), isAppLockDecided(), wasLockOffered()]).then(([supported, decided, offered]) => {
      if (live && shouldOfferLock(supported, decided, offered)) setOffer(true);
    });
    return () => {
      live = false;
    };
  }, [signedIn, showLock]);

  const answerOffer = async (accept: boolean) => {
    setOffer(false);
    await markLockOffered();
    // Proving the phone can verify the user first, so turning it on can never lock them out.
    if (accept && (await authenticate(t("prompt"), t("cancel")))) {
      await saveAppLock(true);
      enabled.current = true;
    } else if (!accept) {
      await saveAppLock(false);
    }
  };

  // Hide the app until we know whether it is locked, so nothing flashes first.
  if (locked === null) return null;

  // The app stays mounted underneath, so unlocking returns to the same screen.
  return (
    <>
      {children}
      <Modal visible={offer && !showLock} transparent animationType="fade" onRequestClose={() => void answerOffer(false)}>
        <View style={[styles2.scrim, { backgroundColor: scrimColor(scheme) }]}>
          <View style={[styles2.sheet, { backgroundColor: palette.surface, borderColor: palette.border }]}>
            <View style={[styles2.badge, { backgroundColor: tint(palette.primary, 0.14) }]}>
              <Ionicons name="finger-print" size={34} color={palette.primary} />
            </View>
            <Heading palette={palette} level={2}>{t("offerTitle")}</Heading>
            <Text style={[styles.muted, { color: palette.muted }]}>{t("offerBody")}</Text>
            <Button label={t("offerYes")} palette={palette} onPress={() => void answerOffer(true)} />
            <Button label={t("offerLater")} variant="secondary" palette={palette} onPress={() => void answerOffer(false)} />
          </View>
        </View>
      </Modal>
      {showLock ? (
        <View style={StyleSheet.absoluteFill}>
          <AuthShell themeToggle={false}>
            <View style={{ alignItems: "center", gap: 6 }}>
              <DepthLogo size={0.8} />
              <Heading palette={palette}>{t("title")}</Heading>
            </View>
            <AuthCard>
              <View style={styles2.who}>
                <View style={[styles2.avatar, { backgroundColor: tint(palette.primary, 0.16) }]}>
                  <Text style={{ color: palette.primary, fontSize: 17, fontWeight: "600" }}>{initialOf(identity)}</Text>
                </View>
                <Text numberOfLines={1} style={[styles.muted, { color: palette.foreground, flexShrink: 1 }]}>{identity}</Text>
              </View>
              <Text style={[styles.muted, { color: failed ? palette.danger : palette.muted, textAlign: "center" }]}>{failed ? t("failed") : t("subtitle")}</Text>
              <Button label={failed ? t("retry") : t("unlock")} palette={palette} onPress={() => void unlock()} />
              <Button
                label={t("signOut")}
                variant="secondary"
                palette={palette}
                onPress={() => {
                  setLocked(false);
                  void saveAppLock(false).then(() => supabase.auth.signOut());
                }}
              />
            </AuthCard>
          </AuthShell>
        </View>
      ) : null}
    </>
  );
}

const styles2 = StyleSheet.create({
  scrim: { flex: 1, justifyContent: "center", padding: 24 },
  sheet: { borderWidth: 1, borderRadius: radius.dialog, padding: 24, gap: 14, maxWidth: 420, width: "100%", alignSelf: "center" },
  badge: { width: 64, height: 64, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", alignSelf: "center" },
  who: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 10 },
  avatar: { width: 40, height: 40, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
});
