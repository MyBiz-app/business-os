import type { components } from "@business-os/api-client";
import { formatTime } from "@business-os/i18n/dates";
import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Card, Heading, Screen, styles } from "@/components/ui";
import { useBusiness } from "@/providers/business-provider";
import { useInbox } from "@/providers/inbox-provider";

type Notification = components["schemas"]["Notification"];

/** What the studio did with the client's bookings and declarations, newest first. */
export default function Updates() {
  const t = useTranslations("client.updates");
  const locale = useLocale();
  const { business, palette } = useBusiness();
  const { inbox, refresh, markAllRead } = useInbox();
  const [refreshing, setRefreshing] = useState(false);
  // Unread when the screen opened: still highlighted while the user reads them.
  const [fresh, setFresh] = useState<Set<string>>(new Set());

  useFocusEffect(
    useCallback(() => {
      void refresh().then((loaded) => {
        if (!loaded || loaded.unread === 0) return;
        setFresh(new Set(loaded.items.filter((n) => !n.read_at).map((n) => n.id)));
        void markAllRead();
      });
    }, [refresh, markAllRead]),
  );

  if (!business) return null;
  const day = new Intl.DateTimeFormat(locale, {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: business.time_zone,
  });
  const when = (instant: unknown) =>
    typeof instant === "string"
      ? `${day.format(new Date(instant))} ${formatTime(instant, locale, business.time_zone)}`
      : "";
  const received = new Intl.DateTimeFormat(locale, { dateStyle: "short", timeStyle: "short", timeZone: business.time_zone });

  const message = (n: Notification) => {
    const p = n.payload as Record<string, unknown>;
    const values = {
      service: String(p.service_name ?? ""),
      when: when(p.starts_at),
      previous: when(p.previous_starts_at),
      note: String(p.note ?? ""),
    };
    if (n.kind === "booked_by_studio" && p.status === "waitlisted") return t("kinds.waitlisted_by_studio", values);
    if ((n.kind === "health_approved" || n.kind === "health_rejected") && p.note) {
      return `${t(`kinds.${n.kind}`, values)} ${t("note", values)}`;
    }
    return t(`kinds.${n.kind}`, values);
  };

  const items = inbox?.items ?? [];
  return (
    <Screen
      palette={palette}
      refreshing={refreshing}
      onRefresh={() => {
        setRefreshing(true);
        void refresh().finally(() => setRefreshing(false));
      }}
    >
      <Heading palette={palette}>{t("title")}</Heading>
      {inbox && items.length === 0 && <Text style={[styles.muted, { color: palette.muted }]}>{t("empty")}</Text>}
      {items.length > 0 && (
        <Card palette={palette}>
          {items.map((n, index) => {
            const isNew = fresh.has(n.id);
            return (
              <View
                key={n.id}
                style={[local.row, index > 0 && { borderTopWidth: 1, borderTopColor: palette.border }]}
                accessible
                accessibilityLabel={`${isNew ? `${t("new")}. ` : ""}${message(n)}`}
              >
                <View style={[local.dot, { backgroundColor: isNew ? palette.primary : "transparent" }]} />
                <View style={local.info}>
                  <Text style={[local.text, { color: palette.foreground }, isNew && local.bold]}>{message(n)}</Text>
                  <Text style={[local.meta, { color: palette.muted }]}>{received.format(new Date(n.created_at))}</Text>
                </View>
              </View>
            );
          })}
        </Card>
      )}
    </Screen>
  );
}

const local = StyleSheet.create({
  row: { flexDirection: "row", gap: 10, paddingVertical: 12, alignItems: "flex-start" },
  dot: { width: 8, height: 8, borderRadius: 4, marginTop: 7 },
  info: { flex: 1, gap: 2 },
  text: { fontSize: 15, textAlign: "left" },
  bold: { fontWeight: "600" },
  meta: { fontSize: 13, textAlign: "left" },
});
