import type { components } from "@business-os/api-client";
import { formatTime, todayIn } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useCallback } from "react";
import { Pressable, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { verticalOf } from "@business-os/app-kit/lib/vertical";
import { useBusiness } from "@/providers/business-provider";
import { useSession } from "@business-os/app-kit/providers/session-provider";

type ScheduledSession = components["schemas"]["ScheduledSession"];

function partOfDay(timeZone: string): "morning" | "afternoon" | "evening" {
  const hour = Number(new Intl.DateTimeFormat("en-GB", { hour: "numeric", hourCycle: "h23", timeZone }).format(new Date()));
  return hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening";
}

/** The day at a glance: what's on, how full it is, and a tap into each session. */
export default function Today() {
  const t = useTranslations("business.today");
  const tTerms = useTranslations("terms");
  const locale = useLocale();
  const { api, scope, tenant, palette, can } = useBusiness();
  const { session: auth } = useSession();
  const tenantId = tenant?.id;
  const timeZone = tenant?.time_zone ?? "UTC";

  const load = useCallback(async () => {
    if (!tenantId || !can("schedule.read")) return [] as ScheduledSession[];
    return unwrap(
      await api.GET("/sessions", { params: { ...scope, query: { start: todayIn(timeZone), days: 1 } } }),
    );
  }, [api, scope, tenantId, timeZone, can]);
  const { data, loading, reload } = useLoad(load);
  if (!tenant) return null;

  const sessions = data ?? [];
  const mine = sessions.filter((s) => s.instructor_user_id === auth?.user.id);
  const vertical = verticalOf(tenant);

  const list = (items: ScheduledSession[]) =>
    items.map((session) => {
      const cancelled = session.status === "cancelled";
      return (
        <Pressable
          key={session.id}
          accessibilityRole="button"
          onPress={() => router.push(`/session/${session.id}`)}
          style={({ pressed }) => [{ opacity: pressed ? 0.75 : 1 }]}
        >
          <Card palette={palette}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
              <Text style={{ color: palette.foreground, fontWeight: "700", fontSize: 16 }}>
                {formatTime(session.starts_at, locale, timeZone)}
              </Text>
              <View
                accessible={false}
                style={{ width: 4, height: 34, borderRadius: 2, backgroundColor: session.service.color ?? palette.primary }}
              />
              <View style={{ flex: 1, gap: 2 }}>
                <Text style={{ color: palette.foreground, fontWeight: "600" }}>{session.service.name}</Text>
                <Text style={{ color: palette.muted, fontSize: 13 }}>
                  {cancelled
                    ? t("cancelled")
                    : t("spots", { booked: session.booked, capacity: session.capacity })}
                  {session.waitlisted > 0 && !cancelled ? ` · ${t("waitlist", { count: session.waitlisted })}` : ""}
                </Text>
              </View>
            </View>
          </Card>
        </Pressable>
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
      </View>

      {!can("schedule.read") ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("none")}</Text>
        </Card>
      ) : sessions.length === 0 ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("none")}</Text>
        </Card>
      ) : (
        <>
          {mine.length > 0 && mine.length !== sessions.length && (
            <>
              <Heading palette={palette} level={2}>
                {t("mine")}
              </Heading>
              {list(mine)}
              <Heading palette={palette} level={2}>
                {t("all")}
              </Heading>
            </>
          )}
          {list(sessions)}
        </>
      )}
      <Text style={[styles.muted, { color: palette.muted }]}>{tTerms(`${vertical}.schedule`)}</Text>
    </Screen>
  );
}
