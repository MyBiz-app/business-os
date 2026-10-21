import Ionicons from "@expo/vector-icons/Ionicons";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { Animated, Platform, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslations } from "use-intl";

import { useReducedMotion, PressableScale } from "./motion";
import { Text } from "./text";
import { tint } from "../lib/brand";
import { fixedColors, radius } from "../lib/theme";
import { useTheme } from "../providers/theme-provider";

export type ToastKind = "success" | "error" | "info";
/** An optional button in the toast: "Undo" after a delete, "View" after a create, "Try again" after an error. */
export type ToastAction = { label: string; onPress: () => void };
type Toast = { id: number; kind: ToastKind; message: string; action?: ToastAction };
type ShowToast = (kind: ToastKind, message: string, options?: { action?: ToastAction }) => void;

const ToastContext = createContext<ShowToast | null>(null);

const SHOW_MS = 4000;
const MAX_VISIBLE = 3;
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

/** Shows up to three toasts at once at the bottom of the screen, the newest at the bottom; the same
 * message again replaces the old one. Errors stay until closed. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const counter = useRef(0);
  const show = useCallback<ShowToast>((kind, message, options) => {
    counter.current += 1;
    const toast: Toast = { id: counter.current, kind, message, action: options?.action };
    setToasts((all) => [...all.filter((item) => !(item.kind === kind && item.message === message)), toast].slice(-MAX_VISIBLE));
  }, []);
  const dismiss = useCallback((id: number) => setToasts((all) => all.filter((item) => item.id !== id)), []);
  const value = useMemo(() => show, [show]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      {toasts.length > 0 ? <ToastStack toasts={toasts} onDone={dismiss} /> : null}
    </ToastContext.Provider>
  );
}

function ToastStack({ toasts, onDone }: { toasts: Toast[]; onDone: (id: number) => void }) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.wrap, { pointerEvents: "box-none" }, { bottom: insets.bottom + 88 }]}>
      {toasts.map((toast) => (
        <ToastView key={toast.id} toast={toast} onDone={() => onDone(toast.id)} />
      ))}
    </View>
  );
}

function ToastView({ toast, onDone }: { toast: Toast; onDone: () => void }) {
  const t = useTranslations("common");
  const { palette } = useTheme();
  const reduced = useReducedMotion();
  // A new toast re-renders the stack with fresh callbacks; the timer must not restart each time.
  const done = useRef(onDone);
  useEffect(() => {
    done.current = onDone;
  });
  const progress = useRef(new Animated.Value(0)).current;
  const color = toast.kind === "success" ? palette.success : toast.kind === "info" ? palette.primary : palette.danger;

  useEffect(() => {
    Animated.timing(progress, { toValue: 1, duration: reduced ? 0 : 220, useNativeDriver: Platform.OS !== "web" }).start();
    if (toast.kind === "error") return;
    const timer = setTimeout(() => done.current(), SHOW_MS);
    return () => clearTimeout(timer);
  }, [progress, reduced, toast.kind]);

  return (
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
  );
}

const styles = StyleSheet.create({
  wrap: { position: "absolute", start: 16, end: 16, alignItems: "center", gap: 8 },
  toast: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    maxWidth: 520,
    width: "100%",
    paddingVertical: 12,
    paddingStart: 14,
    paddingEnd: 6,
    borderRadius: radius.control,
    borderWidth: 1,
    boxShadow: "0px 2px 4px rgba(17, 24, 39, 0.08), 0px 10px 28px rgba(17, 24, 39, 0.18)",
  },
  icon: { width: 22, height: 22, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
  action: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: radius.sm },
  actionLabel: { fontSize: 13, fontWeight: "500" },
  message: { flex: 1, fontSize: 15, lineHeight: 21, textAlign: "left" },
  close: { width: 36, height: 36, alignItems: "center", justifyContent: "center" },
});
