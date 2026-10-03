import { addDays, dayOf, formatDay, todayIn } from "@business-os/i18n/dates";
import { useCallback, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { type ClientSession, SessionCard } from "@/components/session-card";
import { Heading, Screen, styles } from "@/components/ui";
import { unwrap } from "@/lib/api";
import { useLoad } from "@/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

const DAYS = 14;

/** The next two weeks, one day at a time. */
export default function Schedule() {
  const t = useTranslations("client.schedule");
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();
  const today = business ? todayIn(business.time_zone) : "";
  const [day, setDay] = useState(today);

  const load = useCallback(async () => {
    if (!business) return [];
    return unwrap(
      await api.GET("/client/sessions", { params: { ...scope, query: { start: todayIn(business.time_zone), days: DAYS } } }),
    );
  }, [api, scope, business]);
  const { data, loading, reload } = useLoad(load);
  const [overrides, setOverrides] = useState<Record<string, ClientSession>>({});

  if (!business) return null;
  const days = Array.from({ length: DAYS }, (_, i) => addDays(today, i));
  const sessions = (data ?? [])
    .map((s) => overrides[s.id] ?? s)
    .filter((s) => dayOf(s.starts_at, business.time_zone) === day);

  return (
    <Screen
      palette={palette}
      refreshing={loading}
      onRefresh={() => {
        setOverrides({});
        void reload();
      }}
    >
      <Heading palette={palette}>{t("title")}</Heading>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={local.days}>
        {days.map((value) => {
          const selected = value === day;
          return (
            <Pressable
              key={value}
              accessibilityRole="tab"
              accessibilityState={{ selected }}
              accessibilityLabel={formatDay(value, locale, { weekday: "long", day: "numeric", month: "long" })}
              onPress={() => setDay(value)}
              style={[
                local.day,
                { borderColor: palette.border, backgroundColor: selected ? palette.primary : palette.surface },
              ]}
            >
              <Text style={[local.weekday, { color: selected ? palette.onPrimary : palette.muted }]}>
                {value === today ? t("today") : formatDay(value, locale, { weekday: "short" })}
              </Text>
              <Text style={[local.date, { color: selected ? palette.onPrimary : palette.foreground }]}>
                {formatDay(value, locale, { day: "numeric" })}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>

      {sessions.length === 0 ? (
        <Text style={[styles.muted, { color: palette.muted }]}>{loading ? "…" : t("empty")}</Text>
      ) : (
        <View style={local.list}>
          {sessions.map((session) => (
            <SessionCard
              key={session.id}
              session={session}
              onChange={(changed) => setOverrides((current) => ({ ...current, [changed.id]: changed }))}
            />
          ))}
        </View>
      )}
    </Screen>
  );
}

const local = StyleSheet.create({
  days: { gap: 8, paddingVertical: 2 },
  day: { width: 56, paddingVertical: 10, borderRadius: 14, borderWidth: 1, alignItems: "center", gap: 2 },
  weekday: { fontSize: 12, fontWeight: "600" },
  date: { fontSize: 18, fontWeight: "700" },
  list: { gap: 12 },
});
