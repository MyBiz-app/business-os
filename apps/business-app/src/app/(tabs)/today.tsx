import type { components } from "@business-os/api-client";
import Ionicons from "@expo/vector-icons/Ionicons";
import { addDays, dayOf, formatDay, formatTime, todayIn } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Badge, ListRow, PillRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { termsFor } from "@business-os/app-kit/lib/vertical";
import { useBusiness } from "@/providers/business-provider";
import { useSession } from "@business-os/app-kit/providers/session-provider";

type ScheduledSession = components["schemas"]["ScheduledSession"];
type AttentionList = components["schemas"]["AttentionList"];

const DAYS = 7;

function partOfDay(timeZone: string): "morning" | "afternoon" | "evening" {
  const hour = Number(new Intl.DateTimeFormat("en-GB", { hour: "numeric", hourCycle: "h23", timeZone }).format(new Date()));
  return hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening";
}

/** The week ahead one day at a time: what's on, how full it is, a tap into each session, and on
 * today what needs the owner's attention. */
export default function Today() {
  const t = useTranslations("business.today");
  const tTerms = useTranslations("terms");
  const tAttention = useTranslations("dashboard.attention");
  const tReserve = useTranslations("business.reserve");
  const tJobs = useTranslations("jobs");
  const locale = useLocale();
  const { api, scope, tenant, palette, can, branch } = useBusiness();
  const { session: auth } = useSession();
  const tenantId = tenant?.id;
  const timeZone = tenant?.time_zone ?? "UTC";
  const today = todayIn(timeZone);
  const [day, setDay] = useState(today);
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!tenantId) return { sessions: [] as ScheduledSession[], attention: [] as AttentionList[], courts: 0, onSite: false };
    const [sessions, attention, courts, onSite] = await Promise.all([
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
    ]);
    return { sessions, attention, courts, onSite };
  }, [api, scope, tenantId, timeZone, can]);
  const { data, loading, reload } = useLoad(load);
  if (!tenant) return null;

  const all = data?.sessions ?? [];
  const sessions = all.filter((s) => dayOf(s.starts_at, timeZone) === day);
  const mine = sessions.filter((s) => s.instructor_user_id === auth?.user.id);
  const attention = day === today ? (data?.attention ?? []).filter((list) => list.count > 0) : [];
  const terms = termsFor(tenant);
  const short = (value: string) => formatDay(value, locale, { day: "numeric", month: "short" });

  const days = Array.from({ length: DAYS }, (_, i) => addDays(today, i)).map((value) => {
    const count = all.filter((s) => dayOf(s.starts_at, timeZone) === value && s.status !== "cancelled").length;
    const long = formatDay(value, locale, { weekday: "long", day: "numeric", month: "long" });
    return {
      value,
      label: formatDay(value, locale, { day: "numeric" }),
      sublabel: value === today ? t("title") : formatDay(value, locale, { weekday: "short" }),
      accessibilityLabel: `${long}, ${t("sessions", { count })}`,
    };
  });

  const list = (items: ScheduledSession[]) =>
    items.map((session) => {
      const cancelled = session.status === "cancelled";
      const full = !cancelled && session.booking_mode === "class" && session.booked >= session.capacity;
      return (
        <ListRow
          key={session.id}
          palette={palette}
          onPress={() => router.push(`/session/${session.id}`)}
          leading={
            <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
              <Text style={{ color: palette.foreground, fontWeight: "700", fontSize: 16, fontVariant: ["tabular-nums"] }}>
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
                    session.waitlisted > 0 ? t("waitlist", { count: session.waitlisted }) : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")
          }
          trailing={
            cancelled ? (
              <Badge label={t("cancelled")} palette={palette} />
            ) : full ? (
              <Badge label={t("full")} tone="primary" palette={palette} />
            ) : undefined
          }
        />
      );
    });

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <View style={{ gap: 4 }}>
        <Text style={[styles.muted, { color: palette.primary }]}>
          {t("greeting", { part: partOfDay(timeZone) })} ·{" "}
          {new Intl.DateTimeFormat(locale, { weekday: "long", day: "numeric", month: "long", timeZone }).format(new Date())}
        </Text>
        <Heading palette={palette}>{tenant.name}</Heading>
        {branch && <Text style={[styles.muted, { color: palette.muted }]}>{branch.name}</Text>}
      </View>

      {data?.onSite && <Button label={tJobs("cta")} palette={palette} onPress={() => router.push("/jobs")} />}

      {(data?.courts ?? 0) > 0 && (
        <Button label={tReserve("cta")} palette={palette} onPress={() => router.push("/reserve")} />
      )}

      {can("schedule.read") && (
        <View style={{ gap: 10 }}>
          <SectionTitle title={tTerms(`${terms}.schedule`)} palette={palette} />
          <PillRow label={t("days")} options={days} value={day} onChange={setDay} palette={palette} />
        </View>
      )}

      {!can("schedule.read") || sessions.length === 0 ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>
            {loading ? "…" : day === today ? t("none") : t("noneOnDay")}
          </Text>
        </Card>
      ) : (
        <View style={{ gap: 10 }}>
          {mine.length > 0 && mine.length !== sessions.length && (
            <>
              <SectionTitle title={t("mine")} palette={palette} />
              {list(mine)}
              <SectionTitle title={t("all")} palette={palette} />
            </>
          )}
          {list(sessions)}
        </View>
      )}
      {attention.length > 0 && (
        <View style={{ gap: 10 }}>
          <SectionTitle title={t("attention")} palette={palette} />
          {attention.map((group) => {
            const expanded = open === group.kind;
            return (
              <Card key={group.kind} palette={palette}>
                <Pressable
                  accessibilityRole="button"
                  aria-expanded={expanded}
                  accessibilityLabel={`${tAttention(`kinds.${group.kind}`)}, ${group.count}`}
                  onPress={() => setOpen(expanded ? null : group.kind)}
                  style={{ flexDirection: "row", alignItems: "center", gap: 8, minHeight: 32 }}
                >
                  <Text style={{ color: palette.foreground, fontWeight: "700", flex: 1, textAlign: "left" }}>
                    {tAttention(`kinds.${group.kind}`)}
                  </Text>
                  <Badge label={String(group.count)} tone={group.kind === "leads_due" ? "primary" : "danger"} palette={palette} />
                  <Ionicons name={expanded ? "chevron-up" : "chevron-down"} size={18} color={palette.muted} />
                </Pressable>
                {expanded &&
                  group.items.map((item) => (
                    <ListRow
                      key={item.id}
                      palette={palette}
                      title={item.name}
                      subtitle={item.date ? tAttention(`dates.${group.kind}`, { date: short(item.date) }) : tAttention("never")}
                      onPress={() => router.push(group.kind === "leads_due" ? `/lead/${item.id}` : `/client/${item.id}`)}
                    />
                  ))}
              </Card>
            );
          })}
        </View>
      )}
    </Screen>
  );
}
