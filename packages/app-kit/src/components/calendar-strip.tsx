import { addDays, formatDay, monthGrid, monthStart, weekStart } from "@business-os/i18n/dates";
import { useEffect, useRef } from "react";
import { FlatList, Platform, Pressable, StyleSheet, View, useWindowDimensions } from "react-native";
import { useLocale } from "use-intl";

import { Chip } from "./chip";
import { Text } from "./text";
import type { CalendarView } from "../lib/calendar-range";
import type { Palette } from "../lib/theme";
import { radius } from "../lib/theme";

const ITEM = 56;
const GAP = 8;
const STRIDE = ITEM + GAP;
const SPAN = 365; // days shown each side of the anchor; the anchor moves when the selection nears an edge

type StripProps = {
  /** The selected day, kept in the middle. */
  selected: string;
  /** "Today" in the business's time zone; also where the strip starts. */
  today: string;
  onSelect: (day: string) => void;
  /** Days that have something on (a dot under the date). */
  marked: ReadonlySet<string>;
  /** Days the business is closed. */
  closed: ReadonlySet<string>;
  palette: Palette;
  todayLabel: string;
  closedLabel: string;
};

/** A horizontal strip of days with the selected one centred; swipe to move, tap to jump. */
export function DayStrip({ selected, today, onSelect, marked, closed, palette, todayLabel, closedLabel }: StripProps) {
  const locale = useLocale();
  const { width } = useWindowDimensions();
  const list = useRef<FlatList<string>>(null);
  const anchor = useRef(selected);
  // Re-anchor only when the selection leaves the rendered window.
  const offset = Math.round((Date.parse(`${selected}T00:00:00Z`) - Date.parse(`${anchor.current}T00:00:00Z`)) / 86_400_000);
  if (Math.abs(offset) > SPAN - 30) anchor.current = selected;
  // A browser's right-to-left scroll positions run negative, which the list's windowing cannot follow. There the
  // row is laid out left-to-right with the days listed backwards: it reads the same, and scrolls normally.
  const flipped = Platform.OS === "web" && typeof document !== "undefined" && document.documentElement.dir === "rtl";
  const chronological = Array.from({ length: SPAN * 2 + 1 }, (_, i) => addDays(anchor.current, i - SPAN));
  const days = flipped ? chronological.reverse() : chronological;
  const chronologicalIndex = SPAN + Math.round((Date.parse(`${selected}T00:00:00Z`) - Date.parse(`${anchor.current}T00:00:00Z`)) / 86_400_000);
  const index = flipped ? days.length - 1 - chronologicalIndex : chronologicalIndex;
  const side = Math.max(0, (width - 32 - ITEM) / 2);

  useEffect(() => {
    list.current?.scrollToOffset({ offset: index * STRIDE, animated: true });
  }, [index]);

  return (
    <FlatList
      ref={list}
      horizontal
      data={days}
      keyExtractor={(d) => d}
      accessibilityRole="tablist"
      showsHorizontalScrollIndicator={false}
      snapToInterval={STRIDE}
      decelerationRate="fast"
      initialScrollIndex={index}
      getItemLayout={(_, i) => ({ length: STRIDE, offset: STRIDE * i, index: i })}
      windowSize={7}
      initialNumToRender={15}
      style={flipped ? { direction: "ltr" } : undefined}
      contentContainerStyle={{ paddingHorizontal: side, paddingVertical: 2 }}
      onMomentumScrollEnd={(e) => {
        const i = Math.round(Math.abs(e.nativeEvent.contentOffset.x) / STRIDE);
        const day = days[Math.min(days.length - 1, Math.max(0, i))];
        if (day && day !== selected) onSelect(day);
      }}
      renderItem={({ item }) => {
        const isSelected = item === selected;
        const isClosed = closed.has(item);
        return (
          <Pressable
            role="tab"
            aria-selected={isSelected}
            accessibilityLabel={`${formatDay(item, locale, { weekday: "long", day: "numeric", month: "long" })}${isClosed ? `, ${closedLabel}` : ""}`}
            onPress={() => onSelect(item)}
            style={[
              local.day,
              { marginEnd: GAP, borderColor: palette.border, backgroundColor: isSelected ? palette.primary : palette.surface },
              isSelected && local.daySelected,
            ]}
          >
            <Text style={[local.weekday, { color: isSelected ? palette.onPrimary : palette.muted }]}>
              {item === today ? todayLabel : formatDay(item, locale, { weekday: "narrow" })}
            </Text>
            <Text style={[local.date, { color: isSelected ? palette.onPrimary : palette.foreground }]}>
              {formatDay(item, locale, { day: "numeric" })}
            </Text>
            <View
              style={[
                local.dot,
                { backgroundColor: isSelected ? palette.onPrimary : palette.primary, opacity: marked.has(item) && !isClosed ? 1 : 0 },
              ]}
            />
          </Pressable>
        );
      }}
    />
  );
}

type SwitchProps = {
  view: CalendarView;
  onChange: (view: CalendarView) => void;
  palette: Palette;
  labels: Record<CalendarView, string>;
};

/** Day / week / month. */
export function CalendarViewSwitch({ view, onChange, palette, labels }: SwitchProps) {
  return (
    <View role="tablist" style={local.switch}>
      {(["day", "week", "month"] as const).map((v) => (
        <Chip key={v} role="tab" label={labels[v]} selected={view === v} onPress={() => onChange(v)} palette={palette} />
      ))}
    </View>
  );
}

type MonthProps = {
  selected: string;
  today: string;
  marked: ReadonlySet<string>;
  closed: ReadonlySet<string>;
  /** Tapping a day goes down to that day. */
  onPick: (day: string) => void;
  palette: Palette;
};

/** The month as a grid of weeks (Sunday first), a dot on days with activity. */
export function MonthGrid({ selected, today, marked, closed, onPick, palette }: MonthProps) {
  const locale = useLocale();
  const { start, days } = monthGrid(selected);
  const month = monthStart(selected).slice(0, 7);
  const weeks = Array.from({ length: days / 7 }, (_, w) => Array.from({ length: 7 }, (_, d) => addDays(start, w * 7 + d)));
  return (
    <View style={local.month}>
      <View style={local.weekRow}>
        {weeks[0].map((d) => (
          <Text key={d} style={[local.head, { color: palette.muted }]}>
            {formatDay(d, locale, { weekday: "narrow" })}
          </Text>
        ))}
      </View>
      {weeks.map((week) => (
        <View key={week[0]} style={local.weekRow}>
          {week.map((d) => {
            const inMonth = d.startsWith(month);
            const isSelected = d === selected;
            return (
              <Pressable
                key={d}
                accessibilityRole="button"
                accessibilityState={{ selected: isSelected }}
                accessibilityLabel={formatDay(d, locale, { weekday: "long", day: "numeric", month: "long" })}
                onPress={() => onPick(d)}
                style={[
                  local.cell,
                  isSelected && { backgroundColor: palette.primary },
                  d === today && !isSelected && { borderColor: palette.primary, borderWidth: 1 },
                  { opacity: inMonth ? 1 : 0.35 },
                ]}
              >
                <Text
                  style={{
                    color: isSelected ? palette.onPrimary : closed.has(d) ? palette.muted : palette.foreground,
                    fontWeight: "500",
                  }}
                >
                  {formatDay(d, locale, { day: "numeric" })}
                </Text>
                <View
                  style={[
                    local.dot,
                    { backgroundColor: isSelected ? palette.onPrimary : palette.primary, opacity: marked.has(d) ? 1 : 0 },
                  ]}
                />
              </Pressable>
            );
          })}
        </View>
      ))}
    </View>
  );
}

/** The seven days of the week containing `day` (Sunday first). */
export function weekDays(day: string): string[] {
  const start = weekStart(day);
  return Array.from({ length: 7 }, (_, i) => addDays(start, i));
}

const local = StyleSheet.create({
  day: { width: ITEM, minHeight: 76, paddingVertical: 8, borderRadius: radius.dialog, borderWidth: 1, alignItems: "center", justifyContent: "center", gap: 2 },
  daySelected: { minHeight: 84 },
  weekday: { fontSize: 12, fontWeight: "500" },
  date: { fontSize: 17, fontWeight: "600" },
  dot: { width: 5, height: 5, borderRadius: 3 },
  switch: { flexDirection: "row", gap: 8 },
  month: { gap: 6 },
  weekRow: { flexDirection: "row" },
  head: { flex: 1, textAlign: "center", fontSize: 12, fontWeight: "500" },
  cell: { flex: 1, aspectRatio: 1, borderRadius: radius.control, alignItems: "center", justifyContent: "center", gap: 2 },
});
