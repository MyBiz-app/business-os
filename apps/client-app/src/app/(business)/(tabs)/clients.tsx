import type { components } from "@business-os/api-client";
import { formatDay, todayIn } from "@business-os/i18n/dates";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { Avatar, ListRow, PillRow } from "@business-os/app-kit/components/rows";
import { Button, Card, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { termsFor } from "@business-os/app-kit/lib/vertical";
import { useStaff } from "@/providers/staff-provider";

type Filter = "all" | "valid" | "none" | "absent";
const PAGE = 30;
const ABSENT_DAYS = 14; // same window as the reports page and the dashboard

/** The business's clients: search, quick filters, each one's plan and last visit, and adding one. */
type ClientItem = components["schemas"]["ClientListItem"];

export default function Clients() {
  const t = useTranslations("business.clients");
  const tList = useTranslations("clients.list");
  const tClients = useTranslations("clients");
  const tTerms = useTranslations("terms");
  const locale = useLocale();
  const { api, scope, tenant, palette, can } = useStaff();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  // A number on the Numbers screen opens this list already narrowed (`?filter=absent`).
  const { filter: requested } = useLocalSearchParams<{ filter?: string }>();
  useEffect(() => {
    if (requested === "all" || requested === "valid" || requested === "none" || requested === "absent") setFilter(requested);
  }, [requested]);
  // Pages loaded after the first one; cleared whenever the search or filter changes.
  const [more, setMore] = useState<ClientItem[]>([]);
  const [loadingMore, setLoadingMore] = useState(false);
  const tenantId = tenant?.id;

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
              limit: PAGE,
              offset,
            },
          },
        }),
      ),
    [api, scope, query, filter],
  );
  const load = useCallback(async () => {
    setMore([]);
    if (!tenantId) return { items: [], total: 0 };
    return fetchPage(0);
  }, [fetchPage, tenantId]);
  const { data, loading, reload } = useLoad(load);
  if (!tenant) return null;
  const terms = termsFor(tenant);
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
          <Heading palette={palette}>{tTerms(`${terms}.clients`)}</Heading>
          {data && <Text style={[styles.muted, { color: palette.muted }]}>{t("total", { count: data.total })}</Text>}
        </View>
        {can("clients.write") && (
          <Button
            label={t("add")}
            accessibilityLabel={tTerms(`${terms}.addClient`)}
            palette={palette}
            onPress={() => router.push("/client/new")}
          />
        )}
      </View>
      <Field
        label={tTerms(`${terms}.searchClients`)}
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
        ]}
      />
      {items.length === 0 ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>
            {loading ? "…" : query ? tTerms(`${terms}.noResults`) : tTerms(`${terms}.noClients`)}
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
            return (
              <ListRow
                key={client.id}
                palette={palette}
                leading={<Avatar name={name} palette={palette} />}
                title={name}
                subtitle={`${plan} · ${lastVisit(client.last_visit)}`}
                onPress={() => router.push(`/client/${client.id}`)}
              />
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
