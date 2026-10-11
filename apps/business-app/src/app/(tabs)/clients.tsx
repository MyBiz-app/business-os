import { formatDay, todayIn } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Avatar, ListRow, PillRow } from "@business-os/app-kit/components/rows";
import { Button, Card, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { termsFor } from "@business-os/app-kit/lib/vertical";
import { useBusiness } from "@/providers/business-provider";

type Filter = "all" | "valid" | "none" | "absent";
const PAGE = 30;
const MAX = 100; // the API's page limit; past it, searching is quicker than scrolling
const ABSENT_DAYS = 14; // same window as the reports page and the dashboard

/** The business's clients: search, quick filters, each one's plan and last visit, and adding one. */
export default function Clients() {
  const t = useTranslations("business.clients");
  const tList = useTranslations("clients.list");
  const tClients = useTranslations("clients");
  const tTerms = useTranslations("terms");
  const locale = useLocale();
  const { api, scope, tenant, palette, can } = useBusiness();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [limit, setLimit] = useState(PAGE);
  const tenantId = tenant?.id;

  const load = useCallback(async () => {
    if (!tenantId) return { items: [], total: 0 };
    return unwrap(
      await api.GET("/clients", {
        params: {
          ...scope,
          query: {
            search: query || undefined,
            plan: filter === "valid" || filter === "none" ? filter : undefined,
            absent_days: filter === "absent" ? ABSENT_DAYS : undefined,
            limit,
          },
        },
      }),
    );
  }, [api, scope, tenantId, query, filter, limit]);
  const { data, loading, reload } = useLoad(load);
  if (!tenant) return null;
  const terms = termsFor(tenant);
  const today = todayIn(tenant.time_zone);
  const items = data?.items ?? [];

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
          setLimit(PAGE);
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
          setLimit(PAGE);
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
          {data && data.total > items.length &&
            (limit < MAX ? (
              <Button
                label={t("more")}
                variant="secondary"
                palette={palette}
                busy={loading}
                onPress={() => setLimit((current) => Math.min(current + PAGE, MAX))}
              />
            ) : (
              <Text style={[styles.muted, { color: palette.muted }]}>{t("refine")}</Text>
            ))}
        </View>
      )}
    </Screen>
  );
}
