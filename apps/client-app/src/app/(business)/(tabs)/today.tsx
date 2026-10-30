import type { components } from "@business-os/api-client";
import { addDays, dayOf, formatDay, formatTime, todayIn } from "@business-os/i18n/dates";
import { usageWarnings } from "@business-os/i18n/usage";
import { router } from "expo-router";
import Ionicons from "@expo/vector-icons/Ionicons";
import { useCallback, useState } from "react";
import { Linking, Pressable, StyleSheet, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { Badge, ListRow, PillRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Sheet } from "@business-os/app-kit/components/sheet";
import { EmptyState, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { formatMoney } from "@business-os/app-kit/lib/money";
import { font } from "@business-os/app-kit/lib/typography";
import { WEB_URL } from "@business-os/app-kit/lib/env";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { radius } from "@business-os/app-kit/lib/theme";
import { NeedsYou } from "@/components/needs-you";
import { NowCard } from "@/components/now-card";
import { buildTimeline, focusSession, type TimelineState } from "@/lib/day-timeline";
import { useStaff } from "@/providers/staff-provider";
import { useSession } from "@business-os/app-kit/providers/session-provider";

type ScheduledSession = components["schemas"]["ScheduledSession"];
type AttentionList = components["schemas"]["AttentionList"];
type MetricValue = components["schemas"]["MetricValue"];

const DAYS = 7;
/** The four numbers of the morning, as on the web; every other number lives in Numbers. */
const TILES = ["revenue", "active_clients", "attendance", "new_clients"] as const;
const TILE_DAYS = 30;

function partOfDay(timeZone: string): "morning" | "afternoon" | "evening" {
  const hour = Number(new Intl.DateTimeFormat("en-GB", { hour: "numeric", hourCycle: "h23", timeZone }).format(new Date()));
  return hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening";
}

/** The week ahead one day at a time: what's on, how full it is, a tap into each session, and on
 * today what needs the owner's attention. */
export default function Today() {
  const t = useTranslations("business.today");
  const tAi = useTranslations("business.ai");
  const tContent = useTranslations("business.content");
  const tUsage = useTranslations("billing.usage");
  const tReserve = useTranslations("business.reserve");
  const tJobs = useTranslations("jobs");
  const tMetrics = useTranslations("metrics");
  const tDash = useTranslations("dashboard");
  const tWaitlist = useTranslations("dashboard.waitlist");
  const tClients = useTranslations("business.clients");
  const locale = useLocale();
  const { api, scope, tenant, palette, can, branch } = useStaff();
  const { session: auth } = useSession();
  const tenantId = tenant?.id;
  const timeZone = tenant?.time_zone ?? "UTC";
  const today = todayIn(timeZone);
  const [day, setDay] = useState(today);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    if (!tenantId)
      return { sessions: [] as ScheduledSession[], attention: [] as AttentionList[], courts: 0, onSite: false, usage: null, waitlist: null, metrics: [] as MetricValue[] };
    // Up to yesterday: today is still going and would make every change look like a drop.
    const end = addDays(todayIn(timeZone), -1);
    const [sessions, attention, courts, onSite, usage, waitlist, metrics] = await Promise.all([
      can("schedule.read")
        ? api.GET("/sessions", { params: { ...scope, query: { start: todayIn(timeZone), days: DAYS } } }).then(unwrap)
        : Promise.resolve([] as ScheduledSession[]),
      // Not essential: the day still shows if this list can't be loaded.
      api.GET("/attention", { params: scope }).then(unwrap).catch(() => [] as AttentionList[]),
      // Courts and rooms rented by the hour, if the business has any.
      can("bookings.manage")
        ? api
            .GET("/resources", { params: scope })
            .then((r) => (r.data ?? []).filter((s) => s.rooms.length > 0).length)
            .catch(() => 0)
        : Promise.resolve(0),
      // On-site jobs (#42): a technician's day at the clients' addresses.
      api
        .GET("/services", { params: { ...scope, query: { active: true } } })
        .then((r) => (r.data ?? []).some((s) => s.on_site))
        .catch(() => false),
      // Space and messages against the bundle (#104), for whoever manages the business.
      can("business.settings")
        ? api.GET("/billing/usage", { params: scope }).then(unwrap).catch(() => null)
        : Promise.resolve(null),
      can("schedule.read")
        ? api.GET("/waitlist/summary", { params: scope }).then((r) => r.data ?? null).catch(() => null)
        : Promise.resolve(null),
      can("reports.read")
        ? api
            .GET("/metrics", { params: { ...scope, query: { start: addDays(end, -(TILE_DAYS - 1)), end, keys: [...TILES] } } })
            .then(unwrap)
            .catch(() => [] as MetricValue[])
        : Promise.resolve([] as MetricValue[]),
    ]);
    return { sessions, attention, courts, onSite, usage, waitlist, metrics };
  }, [api, scope, tenantId, timeZone, can]);
  const { data, loading, reload } = useLoad(load);
  if (!tenant) return null;

  const all = data?.sessions ?? [];
  const sessions = all.filter((s) => dayOf(s.starts_at, timeZone) === day);
  const mine = sessions.filter((s) => s.instructor_user_id === auth?.user.id);
  const attention = (data?.attention ?? []).filter((list) => list.count > 0);
  const number = new Intl.NumberFormat(locale);
  const showMetric = (metric: MetricValue) => {
    if (metric.value === null) return "-";
    return metric.unit === "money" ? formatMoney(Math.round(metric.value), tenant.currency, locale) : number.format(metric.value);
  };
  const change = (metric: MetricValue) => {
    if (metric.value === null || metric.previous === null || metric.previous === 0) return null;
    const rounded = Math.round(((metric.value - metric.previous) / Math.abs(metric.previous)) * 100) || 0;
    const good = metric.higher_is_better ? rounded > 0 : rounded < 0;
    return { text: `${rounded > 0 ? "+" : ""}${number.format(rounded)}%`, good, flat: rounded === 0 };
  };

  const days = Array.from({ length: DAYS }, (_, i) => addDays(today, i)).map((value) => {
    const count = all.filter((s) => dayOf(s.starts_at, timeZone) === value && s.status !== "cancelled").length;
    const long = formatDay(value, locale, { weekday: "long", day: "numeric", month: "long" });
    return {
      value,
      label: formatDay(value, locale, { day: "numeric" }),
      sublabel: value === today ? t("title") : formatDay(value, locale, { weekday: "short" }),
      count,
      accessibilityLabel: `${long}, ${t("sessions", { count })}`,
    };
  });

  // Today reads as a timeline: hour headings, a "now" line, and what is over fades back.
  const nowMs = day === today ? Date.now() : null;
  const timeline = buildTimeline(sessions, timeZone, nowMs);
  const focus = nowMs === null ? null : focusSession(sessions, nowMs);
  const stateOf = new Map<string, TimelineState>();
  for (const item of timeline) if (item.kind === "session") stateOf.set(item.session.id, item.state);

  const row = (session: ScheduledSession) => {
      const cancelled = session.status === "cancelled";
      const state = stateOf.get(session.id) ?? "upcoming";
      const full = !cancelled && session.booking_mode === "class" && session.booked >= session.capacity;
      return (
        <View key={session.id} style={state === "past" ? local.past : undefined}>
        <ListRow
          palette={palette}
          onPress={() => router.push(`/session/${session.id}`)}
          leading={
            <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
              <Text style={{ color: palette.foreground, fontWeight: "600", fontSize: 15, fontVariant: ["tabular-nums"] }}>
                {formatTime(session.starts_at, locale, timeZone)}
              </Text>
              <View
                accessible={false}
                style={{ width: 4, height: 34, borderRadius: 2, backgroundColor: session.service.color ?? palette.primary }}
              />
            </View>
          }
          title={session.service.name}
          subtitle={
            cancelled
              ? t("cancelled")
              : session.booking_mode === "appointment"
                ? session.appointment_client
                : [
                    t("spots", { booked: session.booked, capacity: session.capacity }),
                    session.waitlisted + session.waiting_requests > 0 ? t("waitlist", { count: session.waitlisted + session.waiting_requests }) : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")
          }
          trailing={
            cancelled ? (
              <Badge label={t("cancelled")} palette={palette} />
            ) : full ? (
              <Badge label={t("full")} tone="primary" palette={palette} />
            ) : state === "live" ? (
              <Badge label={t("now")} tone="primary" palette={palette} />
            ) : undefined
          }
        />
        </View>
      );
  };
  const list = (items: ScheduledSession[]) => items.map(row);

  const usageNotices = data?.usage
    ? usageWarnings(data.usage).map(({ key, percent }) => ({
        text: tUsage(key, { percent }),
        over: key.startsWith("over"),
        open: () => void Linking.openURL(`${WEB_URL}/settings/billing`),
      }))
    : [];
  const waiting = data?.waitlist && data.waitlist.waiting > 0
    ? {
        count: data.waitlist.waiting,
        top: data.waitlist.services[0] ? tWaitlist("top", { service: data.waitlist.services[0].name, count: data.waitlist.services[0].waiting }) : undefined,
      }
    : null;
  const metrics = data?.metrics ?? [];
  const quick = [
    can("ai.use") && tenant.modules.some((m) => m === "ai_basic" || m === "ai_pro")
      ? { key: "ai", label: tAi("open"), icon: "sparkles-outline" as const, go: () => router.push("/ai") }
      : null,
    can("social.read") && tenant.modules.includes("social_studio")
      ? { key: "content", label: tContent("open"), icon: "images-outline" as const, go: () => router.push("/content") }
      : null,
    data?.onSite ? { key: "jobs", label: tJobs("cta"), icon: "construct-outline" as const, go: () => router.push("/jobs") } : null,
    (data?.courts ?? 0) > 0 ? { key: "reserve", label: tReserve("cta"), icon: "tennisball-outline" as const, go: () => router.push("/reserve") } : null,
  ].filter((item) => item !== null);

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <View style={{ flexDirection: "row", alignItems: "flex-start", gap: 12 }}>
        <View style={{ flex: 1, gap: 4 }}>
          <Text style={[styles.muted, { color: palette.primaryInk }]}>
            {t("greeting", { part: partOfDay(timeZone) })} ·{" "}
            {new Intl.DateTimeFormat(locale, { weekday: "long", day: "numeric", month: "long", timeZone }).format(new Date())}
          </Text>
          <Heading palette={palette}>{tenant.name}</Heading>
          {branch && <Text style={[styles.muted, { color: palette.muted }]}>{branch.name}</Text>}
        </View>
        {can("clients.read") && (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("search")}
            onPress={() => router.push("/search")}
            hitSlop={4}
            style={[local.iconButton, { borderColor: palette.border, backgroundColor: palette.surface }]}
          >
            <Ionicons name="search-outline" size={20} color={palette.foreground} />
          </Pressable>
        )}
        {can("clients.write") && (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("newTitle")}
            onPress={() => setCreating(true)}
            hitSlop={4}
            style={[local.iconButton, { borderColor: palette.primary, backgroundColor: palette.primary }]}
          >
            <Ionicons name="add" size={22} color={palette.onPrimary} />
          </Pressable>
        )}
      </View>

      {focus && nowMs !== null && can("schedule.read") ? (
        <NowCard session={focus.session} live={focus.live} nowMs={nowMs} timeZone={timeZone} palette={palette} />
      ) : null}

      <NeedsYou lists={attention} usageNotices={usageNotices} waiting={waiting} palette={palette} />

      {can("schedule.read") && (
        <View style={{ gap: 10 }}>
          <SectionTitle title={t("timeline")} palette={palette} />
          <PillRow label={t("days")} options={days} value={day} onChange={setDay} palette={palette} />
        </View>
      )}

      {!can("schedule.read") || sessions.length === 0 ? (
        <EmptyState
          palette={palette}
          loading={loading && !data}
          message={day === today ? t("none") : t("noneOnDay")}
          icon="calendar-clear-outline"
        />
      ) : (
        <View style={{ gap: 10 }}>
          {mine.length > 0 && mine.length !== sessions.length && (
            <>
              <SectionTitle title={t("mine")} palette={palette} />
              {list(mine)}
              <SectionTitle title={t("all")} palette={palette} />
            </>
          )}
          {timeline.map((item) => {
            if (item.kind === "session") return row(item.session);
            if (item.kind === "hour")
              return (
                <Text
                  key={item.key}
                  accessibilityRole="header"
                  style={[local.hour, { color: palette.muted }]}
                >
                  {`${String(item.hour).padStart(2, "0")}:00`}
                </Text>
              );
            return (
              <View key={item.key} accessible accessibilityLabel={t("now")} style={local.nowRow}>
                <View style={[local.nowDot, { backgroundColor: palette.danger }]} />
                <View style={[local.nowLine, { backgroundColor: palette.danger }]} />
                <Text style={[local.nowText, { color: palette.danger }]}>
                  {t("now")} {nowMs !== null ? formatTime(new Date(nowMs).toISOString(), locale, timeZone) : ""}
                </Text>
              </View>
            );
          })}
        </View>
      )}

      {metrics.length > 0 && (
        <View style={{ gap: 10 }}>
          <SectionTitle title={t("numbers")} action={tDash("allReports")} onAction={() => router.push("/numbers")} palette={palette} />
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 10 }}>
            {metrics.map((metric) => {
              const delta = change(metric);
              const label = tMetrics(metric.key);
              const value = showMetric(metric);
              return (
                <View
                  key={metric.key}
                  accessible
                  accessibilityLabel={[label, value, delta?.text].filter(Boolean).join(", ")}
                  style={[local.tile, { backgroundColor: palette.surface, borderColor: palette.border }]}
                >
                  <Text style={{ color: palette.muted, fontSize: 13, ...font.medium, textAlign: "left" }}>{label}</Text>
                  <View style={{ flexDirection: "row", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
                    <Text style={{ color: palette.foreground, fontSize: 24, ...font.semibold, textAlign: "left", fontVariant: ["tabular-nums"] }}>
                      {value}
                    </Text>
                    {delta && (
                      <Text style={{ color: delta.flat ? palette.muted : delta.good ? palette.success : palette.danger, fontSize: 13, ...font.medium }}>
                        {delta.text}
                      </Text>
                    )}
                  </View>
                </View>
              );
            })}
          </View>
        </View>
      )}

      {quick.length > 0 && (
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {quick.map((item) => (
            <Pressable
              key={item.key}
              accessibilityRole="button"
              onPress={item.go}
              style={[local.chip, { borderColor: palette.border, backgroundColor: palette.surface }]}
            >
              <Ionicons name={item.icon} size={18} color={palette.primaryInk} />
              <Text style={{ color: palette.foreground, fontSize: 15, ...font.medium }}>{item.label}</Text>
            </Pressable>
          ))}
        </View>
      )}

      <Sheet visible={creating} onClose={() => setCreating(false)} palette={palette} title={t("newTitle")}>
        <View style={{ gap: 10 }}>
          {can("clients.write") && (
            <ListRow
              palette={palette}
              title={tClients("add")}
              onPress={() => {
                setCreating(false);
                router.push("/client/new");
              }}
            />
          )}
          {tenant.modules.includes("crm") && (
            <ListRow
              palette={palette}
              title={tDash("newLead")}
              onPress={() => {
                setCreating(false);
                router.push("/lead/new");
              }}
            />
          )}
        </View>
      </Sheet>
    </Screen>
  );
}

const local = StyleSheet.create({
  iconButton: { width: 44, height: 44, borderRadius: radius.pill, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  tile: { flexGrow: 1, flexBasis: "45%", borderWidth: 1, borderRadius: radius.card, padding: 14, gap: 4 },
  past: { opacity: 0.5 },
  hour: { fontSize: 13, ...font.semibold, textAlign: "left", fontVariant: ["tabular-nums"], marginTop: 6 },
  nowRow: { flexDirection: "row", alignItems: "center", gap: 6, minHeight: 20 },
  nowDot: { width: 8, height: 8, borderRadius: 4 },
  nowLine: { flex: 1, height: 1.5 },
  nowText: { fontSize: 12, ...font.semibold, fontVariant: ["tabular-nums"] },
  chip: { flexDirection: "row", alignItems: "center", gap: 8, minHeight: 44, paddingHorizontal: 14, borderRadius: radius.pill, borderWidth: 1 },
});
