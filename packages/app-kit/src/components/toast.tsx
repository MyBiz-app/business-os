import Ionicons from "@expo/vector-icons/Ionicons";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { Animated, Platform, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslations } from "use-intl";

import { useReducedMotion, PressableScale } from "./motion";
import { Text } from "./text";
import { tint } from "../lib/brand";
import { useTheme } from "../providers/theme-provider";

export type ToastKind = "success" | "error";
type Toast = { id: number; kind: ToastKind; message: string };
type ShowToast = (kind: ToastKind, message: string) => void;

const ToastContext = createContext<ShowToast | null>(null);

const SHOW_MS = 4000;

/** `const toast = useToast(); toast("success", t("saved"))`: a short message at the bottom of the screen, like the web app's. */
export function useToast(): ShowToast {
  const show = useContext(ToastContext);
  if (!show) throw new Error("useToast must be used inside <ToastProvider>");
  return show;
}

/** Shows one toast at a time at the bottom of the screen; a new one replaces the old. Errors stay a little longer. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toast, setToast] = useState<Toast | null>(null);
  const counter = useRef(0);
  const show = useCallback<ShowToast>((kind, message) => {
    counter.current += 1;
    setToast({ id: counter.current, kind, message });
  }, []);
  const value = useMemo(() => show, [show]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      {toast ? <ToastView key={toast.id} toast={toast} onDone={() => setToast((current) => (current?.id === toast.id ? null : current))} /> : null}
    </ToastContext.Provider>
  );
}

function ToastView({ toast, onDone }: { toast: Toast; onDone: () => void }) {
  const t = useTranslations("common");
  const { palette } = useTheme();
  const insets = useSafeAreaInsets();
  const reduced = useReducedMotion();
  const progress = useRef(new Animated.Value(0)).current;
  const color = toast.kind === "success" ? palette.success : palette.danger;

  useEffect(() => {
    Animated.timing(progress, { toValue: 1, duration: reduced ? 0 : 220, useNativeDriver: Platform.OS !== "web" }).start();
    const timer = setTimeout(onDone, toast.kind === "error" ? SHOW_MS + 2000 : SHOW_MS);
    return () => clearTimeout(timer);
  }, [progress, reduced, onDone, toast.kind]);

  return (
    <View pointerEvents="box-none" style={[styles.wrap, { bottom: insets.bottom + 88 }]}>
      <Animated.View
        accessibilityRole="alert"
        accessibilityLiveRegion="polite"
        style={[
          styles.toast,
          {
            backgroundColor: palette.surface,
            borderColor: tint(color, 0.5),
            opacity: progress,
            transform: [{ translateY: progress.interpolate({ inputRange: [0, 1], outputRange: [16, 0] }) }],
          },
        ]}
      >
        <Ionicons name={toast.kind === "success" ? "checkmark-circle" : "alert-circle"} size={22} color={color} />
        <Text style={[styles.message, { color: palette.foreground }]}>{toast.message}</Text>
        <PressableScale accessibilityRole="button" accessibilityLabel={t("dismiss")} onPress={onDone} style={styles.close}>
          <Ionicons name="close" size={18} color={palette.muted} />
        </PressableScale>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: "absolute", start: 16, end: 16, alignItems: "center" },
  toast: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    maxWidth: 520,
    width: "100%",
    paddingVertical: 12,
    paddingStart: 14,
    paddingEnd: 6,
    borderRadius: 16,
    borderWidth: 1,
    boxShadow: "0px 2px 4px rgba(17, 24, 39, 0.08), 0px 10px 28px rgba(17, 24, 39, 0.18)",
  },
  message: { flex: 1, fontSize: 15, lineHeight: 21, textAlign: "left" },
  close: { width: 36, height: 36, alignItems: "center", justifyContent: "center" },
});
