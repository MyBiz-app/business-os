import type { components } from "@business-os/api-client";
import Ionicons from "@expo/vector-icons/Ionicons";
import { addDays, dayOf, todayIn } from "@business-os/i18n/dates";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { StyleSheet, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { tint } from "@business-os/app-kit/lib/brand";
import { FRESH_MS } from "@business-os/app-kit/lib/query-client";
import { groupByRecency, updateGroup, type UpdateGroup } from "@business-os/app-kit/lib/client-home";
import { Chip } from "@business-os/app-kit/components/chip";
import { PressableScale } from "@business-os/app-kit/components/motion";
import { notificationIcon, useNotificationText } from "@/lib/notification-text";
import { unwrap } from "@business-os/app-kit/lib/api";
import { Button, Card, EmptyState, Heading, Screen } from "@business-os/app-kit/components/ui";
import { useBusiness } from "@/providers/business-provider";
import { useInbox } from "@/providers/inbox-provider";
import { radius } from "@business-os/app-kit/lib/theme";

type Notification = components["schemas"]["Notification"];
const PAGE = 50; // the API's default page size

/** What the business did with the client's bookings and declarations, and what friends did, newest first; filtered by kind. */
export default function Updates() {
  const t = useTranslations("client.updates");
  const tHome = useTranslations("client.homeCards");
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();
  const { inbox, refresh, markAllRead } = useInbox();
  const [refreshing, setRefreshing] = useState(false);
  // Unread when the screen opened: still highlighted while the user reads them.
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  // Older pages loaded on request; the inbox itself only holds the newest page.
  const [older, setOlder] = useState<Notification[]>([]);
  // Where the next older page starts: undefined until a page has been loaded here, null at the end.
  const [cursor, setCursor] = useState<string | null | undefined>(undefined);
  const [loadingMore, setLoadingMore] = useState(false);
  const [filter, setFilter] = useState<UpdateGroup | "all">("all");

  useFocusEffect(
    useCallback(() => {
      void refresh(FRESH_MS).then((loaded) => {
        if (!loaded || loaded.unread === 0) return;
        setFresh(new Set(loaded.items.filter((n) => !n.read_at).map((n) => n.id)));
        void markAllRead();
      });
    }, [refresh, markAllRead]),
  );

  const message = useNotificationText();
  if (!business) return null;
  const received = new Intl.DateTimeFormat(locale, { timeStyle: "short", dateStyle: "short", timeZone: business.time_zone });
  const today = todayIn(business.time_zone);

  const newest = inbox?.items ?? [];
  const seen = new Set(newest.map((n) => n.id));
  const all = [...newest, ...older.filter((n) => !seen.has(n.id))];
  // Only the kinds that exist are offered as filters; "all" is always there.
  const kinds = (["bookings", "friends", "general"] as const).filter((g) => all.some((n) => updateGroup(n.kind) === g));
  const active = filter === "all" || kinds.includes(filter) ? filter : "all";
  const items = active === "all" ? all : all.filter((n) => updateGroup(n.kind) === active);
  const nextCursor = cursor === undefined ? (inbox?.next_cursor ?? null) : cursor;
  const hasMore = nextCursor !== null;

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const next = unwrap(
        await api.GET("/client/notifications", { params: { ...scope, query: { limit: PAGE, after: nextCursor ?? undefined } } }),
      );
      setOlder((current) => [...current, ...next.items]);
      setCursor(next.next_cursor ?? null);
    } catch {
      // The button stays; tapping it again retries.
    } finally {
      setLoadingMore(false);
    }
  };
  return (
    <Screen
      title={t("title")}
      palette={palette}
      refreshing={refreshing}
      onRefresh={() => {
        setRefreshing(true);
        void refresh().finally(() => setRefreshing(false));
      }}
    >
      {kinds.length > 1 && (
        <View accessibilityRole="tablist" accessibilityLabel={t("filter")} style={local.filters}>
          {(["all", ...kinds] as const).map((g) => (
            <Chip
              key={g}
              role="tab"
              label={t(`groups.${g}`)}
              selected={active === g}
              palette={palette}
              onPress={() => setFilter(g)}
            />
          ))}
        </View>
      )}
      {inbox && items.length === 0 && <EmptyState palette={palette} message={t("empty")} />}
      {groupByRecency(items, (n) => n.created_at, (instant) => dayOf(instant, business.time_zone), today, addDays(today, -7)).map((group) => (
        <View key={group.key} style={local.group}>
          <Heading palette={palette} level={2}>
            {tHome(`groups.${group.key}`)}
          </Heading>
          <Card palette={palette}>
            {group.items.map((n, index) => {
              const isNew = fresh.has(n.id);
              return (
                <PressableScale
                  key={n.id}
                  style={[local.row, index > 0 && { borderTopWidth: 1, borderTopColor: palette.border }]}
                  accessible
                  accessibilityRole={n.kind === "waitlist_spot_open" ? "button" : undefined}
                  accessibilityLabel={`${isNew ? `${t("new")}. ` : ""}${message(n)}`}
                  onPress={n.kind === "waitlist_spot_open" ? () => router.push("/waitlist") : undefined}
                >
                  <View style={[local.icon, { backgroundColor: tint(palette.primary, isNew ? 0.2 : 0.1) }]}>
                    <Ionicons name={notificationIcon(n.kind)} size={20} color={palette.primary} />
                  </View>
                  <View style={local.info}>
                    <Text style={[local.text, { color: palette.foreground }, isNew && local.bold]}>{message(n)}</Text>
                    <Text style={[local.meta, { color: palette.muted }]}>{received.format(new Date(n.created_at))}</Text>
                  </View>
                  {isNew && <View aria-hidden style={[local.dot, { backgroundColor: palette.primary }]} />}
                </PressableScale>
              );
            })}
          </Card>
        </View>
      ))}
      {hasMore && <Button label={t("more")} variant="secondary" palette={palette} busy={loadingMore} onPress={() => void loadMore()} />}
    </Screen>
  );
}

const local = StyleSheet.create({
  row: { flexDirection: "row", gap: 10, paddingVertical: 12, alignItems: "flex-start" },
  dot: { width: 8, height: 8, borderRadius: 4, marginTop: 7 },
  group: { gap: 8 },
  filters: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  icon: { width: 36, height: 36, borderRadius: radius.card, alignItems: "center", justifyContent: "center" },
  info: { flex: 1, gap: 2 },
  text: { fontSize: 15, textAlign: "left" },
  bold: { fontWeight: "500" },
  meta: { fontSize: 13, textAlign: "left" },
});
