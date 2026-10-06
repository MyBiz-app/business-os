import { addDays, dayOf, formatDay, todayIn } from "@business-os/i18n/dates";
import Ionicons from "@expo/vector-icons/Ionicons";
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { PressableScale } from "@business-os/app-kit/components/motion";
import { type ClientSession, SessionCard } from "@/components/session-card";
import { Heading, Screen, elevation, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { termsFor } from "@business-os/app-kit/lib/vertical";
import { useBusiness } from "@/providers/business-provider";

const DAYS = 14;

/** The next two weeks, one day at a time. */
export default function Schedule() {
  const t = useTranslations("client.schedule");
  const tAppointment = useTranslations("client.appointment");
  const tCourt = useTranslations("client.court");
  const tTerms = useTranslations("terms");
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();
  const today = business ? todayIn(business.time_zone) : "";
  const [day, setDay] = useState(today);

  const load = useCallback(async () => {
    if (!business) return { sessions: [], closed: [], appointments: [], courts: [] };
    const query = { start: todayIn(business.time_zone), days: DAYS };
    const [sessions, closed, appointments, courts] = await Promise.all([
      api.GET("/client/sessions", { params: { ...scope, query } }),
      api.GET("/client/closed-days", { params: { ...scope, query } }),
      api.GET("/client/appointments/services", { params: scope }),
      api.GET("/client/resources", { params: scope }),
    ]);
    return {
      sessions: unwrap(sessions),
      closed: unwrap(closed),
      appointments: appointments.data ?? [],
      courts: courts.data ?? [],
    };
  }, [api, scope, business]);
  const { data, loading, reload } = useLoad(load);
  const [overrides, setOverrides] = useState<Record<string, ClientSession>>({});

  if (!business) return null;
  const days = Array.from({ length: DAYS }, (_, i) => addDays(today, i));
  const closedDays = new Map((data?.closed ?? []).map((c) => [c.day, c]));
  const closed = closedDays.get(day);
  const sessions = (data?.sessions ?? [])
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
      {(data?.appointments.length ?? 0) > 0 && (
        <PressableScale
          accessibilityRole="button"
          onPress={() => router.push("/appointment")}
          style={[local.cta, elevation.raised, { backgroundColor: palette.primary }]}
        >
          <Ionicons name="calendar-number-outline" size={28} color={palette.onPrimary} />
          <View style={local.ctaText}>
            <Text style={[local.ctaTitle, { color: palette.onPrimary }]}>{tAppointment("cta")}</Text>
            <Text style={[local.ctaSub, { color: palette.onPrimary }]}>{tAppointment("ctaText")}</Text>
          </View>
          <Ionicons name={locale === "he" ? "chevron-back" : "chevron-forward"} size={22} color={palette.onPrimary} />
        </PressableScale>
      )}
      {(data?.courts.length ?? 0) > 0 && (
        <PressableScale
          accessibilityRole="button"
          onPress={() => router.push("/court")}
          style={[local.cta, elevation.raised, { backgroundColor: palette.primary }]}
        >
          <Ionicons name="tennisball-outline" size={28} color={palette.onPrimary} />
          <View style={local.ctaText}>
            <Text style={[local.ctaTitle, { color: palette.onPrimary }]}>{tCourt("cta")}</Text>
            <Text style={[local.ctaSub, { color: palette.onPrimary }]}>{tCourt("ctaText")}</Text>
          </View>
          <Ionicons name={locale === "he" ? "chevron-back" : "chevron-forward"} size={22} color={palette.onPrimary} />
        </PressableScale>
      )}
      <ScrollView
        horizontal
        accessibilityRole="tablist"
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={local.days}
      >
        {days.map((value) => {
          const selected = value === day;
          const isClosed = closedDays.has(value);
          const label = formatDay(value, locale, { weekday: "long", day: "numeric", month: "long" });
          return (
            <Pressable
              key={value}
              accessibilityRole="tab"
              accessibilityState={{ selected }}
              accessibilityLabel={isClosed ? `${label}, ${t("closedShort")}` : label}
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
              {isClosed && (
                <Text style={[local.closed, { color: selected ? palette.onPrimary : palette.muted }]}>
                  {t("closedShort")}
                </Text>
              )}
            </Pressable>
          );
        })}
      </ScrollView>

      {closed && (
        <Text accessibilityRole="alert" style={[styles.muted, { color: palette.foreground }]}>
          {closed.reason ? t("closedReason", { reason: closed.reason }) : t("closed")}
        </Text>
      )}

      {closed && sessions.length === 0 ? null : sessions.length === 0 ? (
        <Text style={[styles.muted, { color: palette.muted }]}>{loading ? "…" : tTerms(`${termsFor(business)}.appEmpty`)}</Text>
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
  closed: { fontSize: 11, fontWeight: "600" },
  list: { gap: 12 },
  cta: { flexDirection: "row", alignItems: "center", gap: 14, borderRadius: 20, padding: 18 },
  ctaText: { flex: 1, gap: 2 },
  ctaTitle: { fontSize: 18, fontWeight: "800", textAlign: "left" },
  ctaSub: { fontSize: 14, textAlign: "left" }, // full opacity: it sits on the brand color
});
