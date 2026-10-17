import Ionicons from "@expo/vector-icons/Ionicons";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { Animated, Platform, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslations } from "use-intl";

import { useReducedMotion, PressableScale } from "./motion";
import { Text } from "./text";
import { tint } from "../lib/brand";
import { fixedColors } from "../lib/theme";
import { useTheme } from "../providers/theme-provider";

export type ToastKind = "success" | "error" | "info";
/** An optional button in the toast: "Undo" after a delete, "View" after a create, "Try again" after an error. */
export type ToastAction = { label: string; onPress: () => void };
type Toast = { id: number; kind: ToastKind; message: string; action?: ToastAction };
type ShowToast = (kind: ToastKind, message: string, options?: { action?: ToastAction }) => void;

const ToastContext = createContext<ShowToast | null>(null);

const SHOW_MS = 4000;
// The card is dark in both themes, like the web app's.
const CARD = fixedColors.toast;
const CARD_INK = fixedColors.toastInk;
const CARD_MUTED = fixedColors.toastMuted;

/** `const toast = useToast(); toast("success", t("saved"))`: a short message at the bottom of the screen, like the web app's. */
export function useToast(): ShowToast {
  const show = useContext(ToastContext);
  if (!show) throw new Error("useToast must be used inside <ToastProvider>");
  return show;
}

/** Shows one toast at a time at the bottom of the screen; a new one replaces the old. Errors stay until closed. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toast, setToast] = useState<Toast | null>(null);
  const counter = useRef(0);
  const show = useCallback<ShowToast>((kind, message, options) => {
    counter.current += 1;
    setToast({ id: counter.current, kind, message, action: options?.action });
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
  const color = toast.kind === "success" ? palette.success : toast.kind === "info" ? palette.primary : palette.danger;

  useEffect(() => {
    Animated.timing(progress, { toValue: 1, duration: reduced ? 0 : 220, useNativeDriver: Platform.OS !== "web" }).start();
    if (toast.kind === "error") return;
    const timer = setTimeout(onDone, SHOW_MS);
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
            backgroundColor: CARD,
            borderColor: tint(CARD_INK, 0.12),
            opacity: progress,
            transform: [{ translateY: progress.interpolate({ inputRange: [0, 1], outputRange: [16, 0] }) }],
          },
        ]}
      >
        <View style={[styles.icon, { backgroundColor: color }]}>
          <Ionicons name={toast.kind === "success" ? "checkmark" : toast.kind === "info" ? "information" : "alert"} size={14} color={fixedColors.white} />
        </View>
        <Text style={[styles.message, { color: CARD_INK }]}>{toast.message}</Text>
        {toast.action ? (
          <PressableScale
            accessibilityRole="button"
            onPress={() => {
              toast.action?.onPress();
              onDone();
            }}
            style={[styles.action, { backgroundColor: tint(CARD_INK, 0.14) }]}
          >
            <Text style={[styles.actionLabel, { color: CARD_INK }]}>{toast.action.label}</Text>
          </PressableScale>
        ) : null}
        <PressableScale accessibilityRole="button" accessibilityLabel={t("dismiss")} onPress={onDone} style={styles.close}>
          <Ionicons name="close" size={18} color={CARD_MUTED} />
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
    borderRadius: 14,
    borderWidth: 1,
    boxShadow: "0px 2px 4px rgba(17, 24, 39, 0.08), 0px 10px 28px rgba(17, 24, 39, 0.18)",
  },
  icon: { width: 22, height: 22, borderRadius: 11, alignItems: "center", justifyContent: "center" },
  action: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8 },
  actionLabel: { fontSize: 14, fontWeight: "600" },
  message: { flex: 1, fontSize: 15, lineHeight: 21, textAlign: "left" },
  close: { width: 36, height: 36, alignItems: "center", justifyContent: "center" },
});
