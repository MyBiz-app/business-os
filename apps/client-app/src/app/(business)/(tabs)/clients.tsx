import type { components } from "@business-os/api-client";
import { addDays, formatDay, todayIn } from "@business-os/i18n/dates";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Linking, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { Avatar, ListRow, PillRow } from "@business-os/app-kit/components/rows";
import { SwipeRow } from "@business-os/app-kit/components/swipe-row";
import { Button, Card, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useTerm } from "@business-os/app-kit/lib/vertical";
import { useStaff } from "@/providers/staff-provider";

type Filter = "all" | "valid" | "none" | "absent" | "new";
const PAGE = 30;
const ABSENT_DAYS = 14; // same window as the reports page and the dashboard
const NEW_DAYS = 30; // "New" without a period from the Numbers screen

/** The business's clients: search, quick filters, each one's plan and last visit, and adding one. */
type ClientItem = components["schemas"]["ClientListItem"];

export default function Clients() {
  const t = useTranslations("business.clients");
  const tList = useTranslations("clients.list");
  const tClients = useTranslations("clients");
  const term = useTerm();
  const locale = useLocale();
  const { api, scope, tenant, palette, can } = useStaff();
  const timeZone = tenant?.time_zone ?? "UTC";
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  // A number on the Numbers screen opens this list already narrowed (`?filter=absent`).
  const { filter: requested, from, to } = useLocalSearchParams<{ filter?: string; from?: string; to?: string }>();
  useEffect(() => {
    if (requested === "all" || requested === "valid" || requested === "none" || requested === "absent" || requested === "new")
      setFilter(requested);
  }, [requested]);
  // Pages loaded after the first one; cleared whenever the search or filter changes.
  const [more, setMore] = useState<ClientItem[]>([]);
  const [loadingMore, setLoadingMore] = useState(false);
  const tenantId = tenant?.id;

  // "New" is the clients who joined in the period the Numbers screen showed, else the last 30 days.
  const joinedFrom = filter === "new" ? (from ?? addDays(todayIn(timeZone), -(NEW_DAYS - 1))) : undefined;
  const joinedTo = filter === "new" ? (to ?? todayIn(timeZone)) : undefined;
  const fetchPage = useCallback(
    async (offset: number) =>
      unwrap(
        await api.GET("/clients", {
          params: {
            ...scope,
            query: {
              search: query || undefined,
              plan: filter === "valid" || filter === "none" ? filter : undefined,
              absent_days: filter === "absent" ? ABSENT_DAYS : undefined,
              joined_from: joinedFrom,
              joined_to: joinedTo,
              limit: PAGE,
              offset,
            },
          },
        }),
      ),
    [api, scope, query, filter, joinedFrom, joinedTo],
  );
  const load = useCallback(async () => {
    setMore([]);
    if (!tenantId) return { items: [], total: 0 };
    return fetchPage(0);
  }, [fetchPage, tenantId]);
  const { data, loading, reload } = useLoad(load);
  if (!tenant) return null;
  const today = todayIn(tenant.time_zone);
  const items = [...(data?.items ?? []), ...more];

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const next = await fetchPage(items.length);
      setMore((current) => [...current, ...next.items]);
    } catch {
      // The button stays; tapping it again retries.
    } finally {
      setLoadingMore(false);
    }
  };

  const lastVisit = (day: string | null | undefined) => {
    if (!day) return tList("never");
    if (day === today) return tList("today");
    const days = Math.round((Date.parse(today) - Date.parse(day)) / 86_400_000);
    return tList("daysAgo", { days });
  };

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <View style={{ flex: 1, gap: 2 }}>
          <Heading palette={palette}>{term(tenant, "clients")}</Heading>
          {data && <Text style={[styles.muted, { color: palette.muted }]}>{t("total", { count: data.total })}</Text>}
        </View>
        {can("clients.write") && (
          <Button
            label={t("add")}
            accessibilityLabel={term(tenant, "addClient")}
            palette={palette}
            onPress={() => router.push("/client/new")}
          />
        )}
      </View>
      {can("clients.write") && (
        <ListRow palette={palette} title={t("messageGroup")} subtitle={t("messageGroupHint")} onPress={() => router.push("/message-group")} />
      )}
      <Field
        label={term(tenant, "searchClients")}
        placeholder={t("searchHint")}
        palette={palette}
        value={search}
        onChangeText={setSearch}
        onSubmitEditing={() => {
          setQuery(search.trim());
        }}
        returnKeyType="search"
        autoCapitalize="none"
      />
      <PillRow<Filter>
        label={tClients("planFilter")}
        palette={palette}
        value={filter}
        onChange={(value) => {
          setFilter(value);
        }}
        options={[
          { value: "all", label: tClients("planAny") },
          { value: "valid", label: tClients("plans.valid") },
          { value: "none", label: tClients("plans.none") },
          { value: "absent", label: tClients("absentDays", { days: ABSENT_DAYS }) },
          { value: "new", label: tClients("newClients") },
        ]}
      />
      {items.length === 0 ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>
            {loading ? "…" : query ? term(tenant, "noResults") : term(tenant, "noClients")}
          </Text>
        </Card>
      ) : (
        <View style={{ gap: 8 }}>
          {items.map((client) => {
            const name = [client.first_name, client.last_name].filter(Boolean).join(" ");
            const plan = client.plan_name
              ? client.plan_ends_on
                ? t("planUntil", {
                    plan: client.plan_name,
                    date: formatDay(client.plan_ends_on, locale, { day: "numeric", month: "short" }),
                  })
                : client.plan_name
              : tList("noPlan");
            const row = (
              <ListRow
                key={client.id}
                palette={palette}
                leading={<Avatar name={name} palette={palette} />}
                title={name}
                subtitle={`${plan} · ${lastVisit(client.last_visit)}`}
                onPress={() => router.push(`/client/${client.id}`)}
              />
            );
            // A shortcut only: the same call button is on the client's card. Clients without a phone have none.
            return client.phone ? (
              <SwipeRow key={client.id} label={t("call")} icon="call" tone="primary" palette={palette} onAction={() => void Linking.openURL(`tel:${client.phone}`)}>
                {row}
              </SwipeRow>
            ) : (
              row
            );
          })}
          {data && data.total > items.length && (
            <Button label={t("more")} variant="secondary" palette={palette} busy={loadingMore} onPress={() => void loadMore()} />
          )}
        </View>
      )}
    </Screen>
  );
}
