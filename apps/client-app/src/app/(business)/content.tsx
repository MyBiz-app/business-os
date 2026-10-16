import { addDays, formatDay, todayIn } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { Badge, ListRow, PillRow, SectionTitle, StatTile, TileGrid } from "@business-os/app-kit/components/rows";
import { BackBar } from "@business-os/app-kit/components/rows";
import { Button, Card, EmptyState, Heading, LoadError, Screen, Skeleton, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { TrendBars } from "@/components/trend-bars";
import { useStaff } from "@/providers/staff-provider";

type Days = "7" | "30" | "90";
const KPIS = ["followers", "reach", "impressions", "video_views", "engagements", "engagement_rate_bp"] as const;
const TOP_SHOWN = 5;

/** The content studio in the business app: connected networks, the main numbers, the best posts,
 * the drafts Sophie prepared, and a way to ask her. The full dashboard stays in the web CRM. */
export default function Content() {
  const t = useTranslations("business.content");
  const tc = useTranslations("content");
  const locale = useLocale();
  const { api, scope, tenant, palette, can } = useStaff();
  const [days, setDays] = useState<Days>("30");
  const [network, setNetwork] = useState("all");
  const [discarding, setDiscarding] = useState<string | null>(null);
  const timeZone = tenant?.time_zone ?? "UTC";
  const canAsk = can("ai.use") && !!tenant?.modules.some((m) => m === "ai_basic" || m === "ai_pro");

  const loadBase = useCallback(async () => {
    const [accounts, drafts] = await Promise.all([
      api.GET("/social/accounts", { params: scope }).then(unwrap),
      api.GET("/social/drafts", { params: scope }).then(unwrap),
    ]);
    return { accounts, drafts };
  }, [api, scope]);
  const base = useLoad(loadBase);

  const loadNumbers = useCallback(async () => {
    if (!base.data || base.data.accounts.length === 0) return null;
    const end = todayIn(timeZone);
    const start = addDays(end, -(Number(days) - 1));
    const networks = network === "all" ? undefined : [network];
    const query = { from: start, to: end, networks };
    const [dashboard, top] = await Promise.all([
      api.GET("/social/dashboard", { params: { ...scope, query: { ...query, compare: true } } }).then(unwrap),
      api.GET("/social/posts/top", { params: { ...scope, query: { ...query, sort: "views", limit: TOP_SHOWN } } }).then(unwrap),
    ]);
    return { dashboard, top };
  }, [api, scope, timeZone, days, network, base.data]);
  const numbers = useLoad(loadNumbers);

  const discard = async (id: string) => {
    setDiscarding(id);
    try {
      await api.DELETE("/social/drafts/{draft_id}", { params: { ...scope, path: { draft_id: id } } });
      await base.reload();
    } finally {
      setDiscarding(null);
    }
  };

  const number = new Intl.NumberFormat(locale);
  const accounts = base.data?.accounts ?? [];
  const drafts = base.data?.drafts ?? [];
  const networks = [...new Set(accounts.map((a) => a.network))];
  const dashboard = numbers.data?.dashboard;
  const top = numbers.data?.top ?? [];
  const show = (key: (typeof KPIS)[number], value: number) =>
    key === "engagement_rate_bp" ? `${new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(value / 100)}%` : number.format(value);
  const changeOf = (value: number, previous: number | null | undefined) => {
    if (previous === null || previous === undefined || previous === 0) return null;
    const rounded = Math.round(((value - previous) / Math.abs(previous)) * 100) || 0;
    return `${rounded > 0 ? "+" : ""}${number.format(rounded)}%`;
  };
  // Followers of every network added up per day, for one trend line.
  const followerPoints = (() => {
    const byDay = new Map<string, number>();
    for (const series of dashboard?.followers_series ?? []) {
      for (const point of series.points) byDay.set(point.day, (byDay.get(point.day) ?? 0) + point.followers);
    }
    return [...byDay.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([bucket, value]) => ({ bucket, value }));
  })();
  const day = (value: string) => formatDay(value, locale, { day: "numeric", month: "short" });
  const demoOnly = accounts.length > 0 && accounts.every((a) => a.is_demo);

  return (
    <Screen palette={palette} refreshing={base.loading && !!base.data} onRefresh={() => void base.reload()}>
      <BackBar label={t("back")} palette={palette} onPress={() => (router.canGoBack() ? router.back() : router.replace("/today"))} />
      <View style={{ gap: 4 }}>
        <Heading palette={palette}>{tc("title")}</Heading>
        <Text style={[styles.muted, { color: palette.muted }]}>{tc("subtitle")}</Text>
      </View>

      {canAsk && <Button label={t("askCreative")} palette={palette} onPress={() => router.push({ pathname: "/ai-chat", params: { agent: "creative", context: "content" } })} />}

      {base.error ? (
        <LoadError palette={palette} onRetry={() => void base.reload()} />
      ) : !base.data ? (
        <Skeleton palette={palette} height={72} />
      ) : accounts.length === 0 ? (
        <EmptyState palette={palette} message={t("noAccounts")} />
      ) : (
        <>
          {demoOnly && <Text style={[styles.muted, { color: palette.muted }]}>{tc("demoBanner")}</Text>}
          <SectionTitle title={t("networks")} palette={palette} />
          {accounts.map((account) => (
            <ListRow
              key={account.id}
              palette={palette}
              title={account.name}
              subtitle={tc(`networks.${account.network}` as never)}
              trailing={
                account.status !== "connected" ? (
                  <Badge label={t("needsReconnect")} tone="danger" palette={palette} />
                ) : account.is_demo ? (
                  <Badge label={t("demo")} palette={palette} />
                ) : undefined
              }
            />
          ))}

          <PillRow
            label={tc("filters.period")}
            palette={palette}
            value={days}
            onChange={setDays}
            options={(["7", "30", "90"] as const).map((value) => ({ value, label: tc(`filters.d${value}`) }))}
          />
          {networks.length > 1 && (
            <PillRow
              label={tc("filters.networks")}
              palette={palette}
              value={network}
              onChange={setNetwork}
              options={[
                { value: "all", label: tc("filters.allNetworks") },
                ...networks.map((value) => ({ value, label: tc(`networks.${value}` as never) })),
              ]}
            />
          )}

          {numbers.error ? (
            <LoadError palette={palette} onRetry={() => void numbers.reload()} />
          ) : !dashboard ? (
            <Skeleton palette={palette} height={96} />
          ) : (
            <>
              <TileGrid>
                {KPIS.map((key) => {
                  const kpi = dashboard.kpis[key];
                  if (!kpi) return null;
                  const change = changeOf(kpi.value, kpi.previous);
                  const label = tc(`kpi.${key}` as never);
                  return <StatTile key={key} palette={palette} label={label} value={[show(key, kpi.value), change].filter(Boolean).join("  ")} />;
                })}
              </TileGrid>
              <SectionTitle title={tc("charts.followersTitle")} palette={palette} />
              <TrendBars
                points={followerPoints}
                label={day}
                value={(value) => number.format(value)}
                empty={tc("charts.noData")}
                palette={palette}
              />
            </>
          )}

          <SectionTitle title={tc("posts.title")} palette={palette} />
          {numbers.data && top.length === 0 && <Text style={[styles.muted, { color: palette.muted }]}>{tc("posts.empty")}</Text>}
          {top.map((post) => (
            <ListRow
              key={post.id}
              palette={palette}
              title={post.caption || tc("posts.untitled")}
              subtitle={`${tc(`networks.${post.network}` as never)} · ${tc(`kinds.${post.kind}` as never)} · ${day(post.published_at.slice(0, 10))}`}
              trailing={<Text style={{ color: palette.foreground, fontWeight: "700" }}>{number.format(post.views)}</Text>}
            />
          ))}
        </>
      )}

      {base.data && (
        <>
          <SectionTitle title={t("drafts")} palette={palette} />
          {drafts.length === 0 ? (
            <Card palette={palette}>
              <Text style={[styles.muted, { color: palette.muted }]}>{t("noDrafts")}</Text>
            </Card>
          ) : (
            drafts.map((draft) => (
              <Card key={draft.id} palette={palette}>
                <View style={{ gap: 8 }}>
                  {draft.network && <Text style={[styles.muted, { color: palette.primary, fontWeight: "700" }]}>{tc(`networks.${draft.network}` as never)}</Text>}
                  <Text style={{ color: palette.foreground, textAlign: "left" }}>{draft.body}</Text>
                  {draft.idea && <Text style={[styles.muted, { color: palette.muted }]}>{draft.idea}</Text>}
                  {can("social.manage") && (
                    <Button label={t("discard")} palette={palette} variant="secondary" busy={discarding === draft.id} onPress={() => void discard(draft.id)} />
                  )}
                </View>
              </Card>
            ))
          )}
          <Text style={[styles.muted, { color: palette.muted }]}>{t("publishHint")}</Text>
        </>
      )}
    </Screen>
  );
}
