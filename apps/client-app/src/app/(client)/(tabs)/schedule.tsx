import { dayOf, formatDay, todayIn } from "@business-os/i18n/dates";
import Ionicons from "@expo/vector-icons/Ionicons";
import { router } from "expo-router";
import * as Notifications from "expo-notifications";
import { useCallback, useState } from "react";
import { Platform, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { CalendarViewSwitch, DayStrip, MonthGrid, weekDays } from "@business-os/app-kit/components/calendar-strip";
import { Chip } from "@business-os/app-kit/components/chip";
import { type CalendarView, stepDay } from "@business-os/app-kit/lib/calendar-range";
import { PressableScale } from "@business-os/app-kit/components/motion";
import { type ClientSession, SessionCard } from "@/components/session-card";
import { Button, Heading, Screen, elevation, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { termsFor } from "@business-os/app-kit/lib/vertical";
import { NO_FILTERS, applyFilters, filterOptions, upcomingRelease, type ClassFilters } from "@/lib/class-filters";
import { useDependents } from "@/lib/use-dependents";
import { useScheduleWindow } from "@/lib/use-schedule-window";
import { useBusiness } from "@/providers/business-provider";

/** The class schedule: a day strip centred on the chosen day, drilling up to a week and a month. */
export default function Schedule() {
  const t = useTranslations("client.schedule");
  const tAppointment = useTranslations("client.appointment");
  const tCourt = useTranslations("client.court");
  const tTerms = useTranslations("terms");
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();
  const dependents = useDependents();
  const today = business ? todayIn(business.time_zone) : "";
  const [day, setDay] = useState(today);

  const [view, setView] = useState<CalendarView>("day");
  const win = useScheduleWindow(view, day);
  const load = useCallback(async () => {
    if (!business) return { appointments: [], courts: [], release: null };
    const [appointments, courts, release] = await Promise.all([
      api.GET("/client/appointments/services", { params: scope }),
      api.GET("/client/resources", { params: scope }),
      api.GET("/client/schedule-release", { params: scope }),
    ]);
    return { appointments: appointments.data ?? [], courts: courts.data ?? [], release: release.data ?? null };
  }, [api, scope, business]);
  const { data, loading: loadingStatic } = useLoad(load);
  const loading = loadingStatic || win.loading;
  const [overrides, setOverrides] = useState<Record<string, ClientSession>>({});
  const [filters, setFilters] = useState<ClassFilters>(NO_FILTERS);
  const [reminded, setReminded] = useState(false);

  if (!business) return null;
  const closedDays = new Map(win.closed.map((c) => [c.day, c]));
  const closed = closedDays.get(day);
  const allSessions = win.sessions.map((s) => overrides[s.id] ?? s);
  const sessions = allSessions.filter((s) => dayOf(s.starts_at, business.time_zone) === day);
  const marked = new Set(allSessions.map((s) => dayOf(s.starts_at, business.time_zone)));
  const closedSet = new Set(closedDays.keys());
  const options = filterOptions(allSessions.filter((s) => s.service.id && s.capacity > 1));
  const visible = applyFilters(sessions, filters);
  const opening = upcomingRelease(data?.release?.next_release_at, Date.now());
  const openingLabel = opening
    ? new Intl.DateTimeFormat(locale, {
        weekday: "long",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: business.time_zone,
      }).format(opening)
    : null;

  // A reminder on this phone for the moment the next week opens (nothing to schedule on the web).
  const remind = async () => {
    if (!opening) return;
    try {
      const { status } = await Notifications.requestPermissionsAsync();
      if (status !== "granted") return;
      await Notifications.scheduleNotificationAsync({
        content: { title: business.name, body: t("releaseReminderBody") },
        trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date: opening },
      });
      setReminded(true);
    } catch {
      // a reminder is a convenience; the schedule works without it
    }
  };

  return (
    <Screen
      palette={palette}
      refreshing={loading}
      onRefresh={() => {
        setOverrides({});
        win.reload();
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
          style={[local.cta, { backgroundColor: palette.surface, borderWidth: 1, borderColor: palette.border }]}
        >
          <Ionicons name="tennisball-outline" size={28} color={palette.primary} />
          <View style={local.ctaText}>
            <Text style={[local.ctaTitle, { color: palette.foreground }]}>{tCourt("cta")}</Text>
            <Text style={[local.ctaSub, { color: palette.muted }]}>{tCourt("ctaText")}</Text>
          </View>
          <Ionicons name={locale === "he" ? "chevron-back" : "chevron-forward"} size={22} color={palette.muted} />
        </PressableScale>
      )}
      <View style={local.bar}>
        <CalendarViewSwitch
          view={view}
          onChange={setView}
          palette={palette}
          labels={{ day: t("viewDay"), week: t("viewWeek"), month: t("viewMonth") }}
        />
        {day !== today && (
          <Chip label={t("today")} selected={false} onPress={() => setDay(today)} palette={palette} role="tab" />
        )}
      </View>
      {view === "month" ? (
        <>
          <View style={local.bar}>
            <Pressable accessibilityRole="button" accessibilityLabel={t("previous")} onPress={() => setDay(stepDay("month", day, -1))}>
              <Ionicons name={locale === "he" ? "chevron-forward" : "chevron-back"} size={24} color={palette.foreground} />
            </Pressable>
            <Text style={[local.monthTitle, { color: palette.foreground }]}>
              {formatDay(day, locale, { month: "long", year: "numeric" })}
            </Text>
            <Pressable accessibilityRole="button" accessibilityLabel={t("next")} onPress={() => setDay(stepDay("month", day, 1))}>
              <Ionicons name={locale === "he" ? "chevron-back" : "chevron-forward"} size={24} color={palette.foreground} />
            </Pressable>
          </View>
          <MonthGrid
            selected={day}
            today={today}
            marked={marked}
            closed={closedSet}
            palette={palette}
            onPick={(picked) => {
              setDay(picked);
              setView("day");
            }}
          />
        </>
      ) : (
        <DayStrip
          selected={day}
          today={today}
          onSelect={setDay}
          marked={marked}
          closed={closedSet}
          palette={palette}
          todayLabel={t("today")}
          closedLabel={t("closedShort")}
        />
      )}

      {closed && (
        <Text accessibilityRole="alert" style={[styles.muted, { color: palette.foreground }]}>
          {closed.reason ? t("closedReason", { reason: closed.reason }) : t("closed")}
        </Text>
      )}

      {options.instructors.length + options.services.length > 1 && (
        <View style={local.filters}>
          {options.instructors.length > 1 && (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={local.chips}>
              <Chip
                role="tab"
                label={t("allInstructors")}
                selected={!filters.instructorId}
                onPress={() => setFilters((f) => ({ ...f, instructorId: null }))}
                palette={palette}
              />
              {options.instructors.map((i) => (
                <Chip
                  key={i.id}
                  role="tab"
                  label={i.name}
                  selected={filters.instructorId === i.id}
                  onPress={() => setFilters((f) => ({ ...f, instructorId: i.id }))}
                  palette={palette}
                />
              ))}
            </ScrollView>
          )}
          {options.services.length > 1 && (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={local.chips}>
              <Chip
                role="tab"
                label={t("allClasses")}
                selected={!filters.serviceId}
                onPress={() => setFilters((f) => ({ ...f, serviceId: null }))}
                palette={palette}
              />
              {options.services.map((sv) => (
                <Chip
                  key={sv.id}
                  role="tab"
                  label={sv.name}
                  selected={filters.serviceId === sv.id}
                  onPress={() => setFilters((f) => ({ ...f, serviceId: sv.id }))}
                  palette={palette}
                />
              ))}
            </ScrollView>
          )}
        </View>
      )}

      {openingLabel && (
        <View style={[local.release, { backgroundColor: palette.surface, borderColor: palette.border }]}>
          <Text style={[styles.muted, { color: palette.foreground }]}>{t("releaseOpens", { when: openingLabel })}</Text>
          {Platform.OS !== "web" && (
            <Button
              label={reminded ? t("reminderSet") : t("remindMe")}
              variant="secondary"
              palette={palette}
              disabled={reminded}
              onPress={() => void remind()}
            />
          )}
        </View>
      )}

      {view === "week" ? (
        <View style={local.list}>
          {weekDays(day).map((d) => {
            const daySessions = applyFilters(
              allSessions.filter((x) => dayOf(x.starts_at, business.time_zone) === d),
              filters,
            );
            if (daySessions.length === 0) return null;
            return (
              <View key={d} style={local.list}>
                <Text style={[local.weekHead, { color: palette.foreground }]}>
                  {formatDay(d, locale, { weekday: "long", day: "numeric", month: "long" })}
                </Text>
                {daySessions.map((session) => (
                  <SessionCard
                    key={session.id}
                    session={session}
                    dependents={dependents}
                    onChange={(changed) => setOverrides((current) => ({ ...current, [changed.id]: changed }))}
                  />
                ))}
              </View>
            );
          })}
          {!loading && weekDays(day).every((d) => !marked.has(d)) && (
            <Text style={[styles.muted, { color: palette.muted }]}>{tTerms(`${termsFor(business)}.appEmpty`)}</Text>
          )}
        </View>
      ) : view === "month" ? null : closed && sessions.length === 0 ? null : visible.length === 0 && sessions.length > 0 ? (
        <Text style={[styles.muted, { color: palette.muted }]}>{t("noMatch")}</Text>
      ) : sessions.length === 0 ? (
        <Text style={[styles.muted, { color: palette.muted }]}>{loading ? "…" : tTerms(`${termsFor(business)}.appEmpty`)}</Text>
      ) : (
        <View style={local.list}>
          {visible.map((session) => (
            <SessionCard
              key={session.id}
              session={session}
              dependents={dependents}
              onChange={(changed) => setOverrides((current) => ({ ...current, [changed.id]: changed }))}
            />
          ))}
        </View>
      )}
    </Screen>
  );
}

const local = StyleSheet.create({
  bar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
  monthTitle: { fontSize: 18, fontWeight: "700" },
  weekHead: { fontSize: 15, fontWeight: "700", marginTop: 4 },
  list: { gap: 12 },
  filters: { gap: 8 },
  chips: { gap: 8, paddingVertical: 2 },
  release: { borderWidth: 1, borderRadius: 20, padding: 14, gap: 10 },
  cta: { flexDirection: "row", alignItems: "center", gap: 14, borderRadius: 24, padding: 18 },
  ctaText: { flex: 1, gap: 2 },
  ctaTitle: { fontSize: 18, fontWeight: "800", textAlign: "left" },
  ctaSub: { fontSize: 14, textAlign: "left" }, // full opacity: it sits on the brand color
});
