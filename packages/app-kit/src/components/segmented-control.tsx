import { Pressable, StyleSheet, Text, View } from "react-native";

import { useTheme } from "../providers/theme-provider";

type Option<T extends string> = { value: T; label: string };

type Props<T extends string> = {
  label: string;
  options: Option<T>[];
  value: T;
  onChange: (value: T) => void;
};

export function SegmentedControl<T extends string>({ label, options, value, onChange }: Props<T>) {
  const { palette } = useTheme();

  return (
    <View style={styles.container}>
      <Text style={[styles.label, { color: palette.muted }]}>{label}</Text>
      <View
        role="radiogroup"
        aria-label={label}
        style={[styles.group, { borderColor: palette.border, backgroundColor: palette.surface }]}
      >
        {options.map((option) => {
          const selected = option.value === value;
          return (
            <Pressable
              key={option.value}
              role="radio"
              aria-checked={selected}
              onPress={() => onChange(option.value)}
              style={[styles.option, selected && { backgroundColor: palette.primary }]}
            >
              <Text style={{ color: selected ? palette.onPrimary : palette.foreground }}>
                {option.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: 8 },
  label: { fontSize: 13, fontWeight: "600" },
  group: { flexDirection: "row", borderWidth: 1, borderRadius: 10, padding: 3, gap: 3 },
  option: { flex: 1, alignItems: "center", paddingVertical: 8, borderRadius: 7 },
});
