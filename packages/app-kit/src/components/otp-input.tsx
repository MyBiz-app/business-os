import { useRef } from "react";
import { Platform, Pressable, StyleSheet, TextInput, type TextInputInstance, View } from "react-native";

import { tint } from "../lib/brand";
import { font } from "../lib/typography";
import type { Palette } from "../lib/theme";
import { Text } from "./text";
import { radius } from "../lib/theme";

/**
 * A one-time code as separate boxes. One hidden input holds the digits, so pasting a whole code
 * (or the code the keyboard suggests from an SMS or email) fills every box, and `onComplete`
 * fires once the last digit is in. Always laid out left to right, like the digits themselves.
 */
export function OtpInput({
  value,
  onChange,
  length,
  palette,
  label,
  onComplete,
  invalid,
}: {
  value: string;
  onChange: (value: string) => void;
  length: number;
  palette: Palette;
  label: string;
  onComplete?: (value: string) => void;
  invalid?: boolean;
}) {
  const input = useRef<TextInputInstance>(null);
  const change = (raw: string) => {
    const digits = raw.replace(/\D/g, "").slice(0, length);
    onChange(digits);
    if (digits.length === length) onComplete?.(digits);
  };
  return (
    <Pressable accessible={false} onPress={() => input.current?.focus()} style={styles.row}>
      {Array.from({ length }, (_, index) => {
        const filled = index < value.length;
        const active = index === Math.min(value.length, length - 1);
        return (
          <View
            key={index}
            style={[
              styles.box,
              {
                backgroundColor: palette.surface,
                borderColor: invalid ? palette.danger : active ? palette.primary : palette.border,
                borderWidth: active || invalid ? 2 : 1,
                boxShadow: active ? `0px 0px 0px 4px ${tint(palette.primary, 0.18)}` : undefined,
              },
            ]}
          >
            <Text style={[styles.digit, { color: palette.foreground }]}>{filled ? value[index] : ""}</Text>
          </View>
        );
      })}
      <TextInput
        ref={input}
        value={value}
        onChangeText={change}
        accessibilityLabel={label}
        keyboardType="number-pad"
        autoComplete={Platform.OS === "android" ? "sms-otp" : "one-time-code"}
        textContentType="oneTimeCode"
        importantForAutofill="yes"
        maxLength={length}
        autoFocus
        caretHidden
        style={styles.hidden}
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  // `direction: "ltr"` pins the order of the boxes whatever the app's layout direction (a right-to-left layout would show the code backwards).
  row: { flexDirection: "row", direction: "ltr", justifyContent: "center", gap: 8 },
  box: { width: 46, height: 58, borderRadius: radius.control, alignItems: "center", justifyContent: "center" },
  digit: { fontSize: 24, ...font.semibold },
  // Covers the boxes and is invisible, so taps and pastes land on it.
  hidden: { position: "absolute", top: 0, bottom: 0, left: 0, right: 0, opacity: 0.02, fontSize: 1, direction: "ltr", textAlign: "left" },
});
