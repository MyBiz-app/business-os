import { addDays, formatDay, todayIn } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Badge, ListRow, PillRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { formatMoney } from "@business-os/app-kit/lib/money";
import type { Palette } from "@business-os/app-kit/lib/theme";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Days = "7" | "30" | "90";
type Trend = "revenue" | "attendance"; // the metrics the API can chart
const KEYS = ["revenue", "active_clients", "attendance", "occupancy", "no_show_rate", "new_clients"] as const;
const AT_RISK_DAYS = 14; // same window as the reports page and the clients filter
const AT_RISK_SHOWN = 5;

/** The numbers the owner checks between clients: key metrics for a period with the change from
 * the period before, a trend, what works best, and the clients to reach out to. */
export default function Numbers() {
  const t = useTranslations("business.numbers");
  const tMetrics = useTranslations("metrics");
  const tReports = useTranslations("reports");
  const locale = useLocale();
  const { api, scope, tenant, palette, branch, branches } = useBusiness();
  const [days, setDays] = useState<Days>("30");
  const [trend, setTrend] = useState<Trend>("revenue");
  const [allAtRisk, setAllAtRisk] = useState(false);
  const timeZone = tenant?.time_zone ?? "UTC";
  const byBranch = !branch && branches.length > 1;

  const load = useCallback(async () => {
    // Up to yesterday: today is still going and would make every change look like a drop.
    const end = addDays(todayIn(timeZone), -1);
    const start = addDays(end, -(Number(days) - 1));
    const period = { start, end };
    const [metrics, services, branchRows, atRisk] = await Promise.all([
      api.GET("/metrics", { params: { ...scope, query: { ...period, keys: [...KEYS] } } }).then(unwrap),
      api
        .GET("/metrics/breakdown/{dimension}", { params: { ...scope, path: { dimension: "service" }, query: period } })
        .then(unwrap),
      byBranch
        ? api
            .GET("/metrics/breakdown/{dimension}", { params: { ...scope, path: { dimension: "branch" }, query: period } })
            .then(unwrap)
        : Promise.resolve([]),
      api.GET("/metrics/members-at-risk", { params: { ...scope, query: { days: AT_RISK_DAYS } } }).then(unwrap),
    ]);
    return { period, metrics, services, branchRows, atRisk };
  }, [api, scope, timeZone, days, byBranch]);
  const { data, loading, reload } = useLoad(load);

  // The trend has its own loader so switching it doesn't reload the whole screen.
  const loadTrend = useCallback(async () => {
    if (!data) return [];
    const grain = days === "90" ? "week" : "day";
    return unwrap(
      await api.GET("/metrics/{key}/series", {
        params: { ...scope, path: { key: trend }, query: { ...data.period, grain } },
      }),
    );
  }, [api, scope, data, trend, days]);
  const { data: points } = useLoad(loadTrend);
  if (!tenant) return null;

  const number = new Intl.NumberFormat(locale);
  const percent = (value: number | null | undefined) =>
    value === null || value === undefined ? "—" : `${number.format(Math.round(value))}%`;
  const show = (unit: string, value: number | null) => {
    if (value === null) return "—";
    if (unit === "money") return formatMoney(Math.round(value), tenant.currency, locale);
    if (unit === "percent") return percent(value);
    return number.format(value);
  };
  const metrics = data?.metrics ?? [];
  const change = (metric: (typeof metrics)[number]) => {
    if (metric.value === null || metric.previous === null || metric.previous === 0) return null;
    const rounded = Math.round(((metric.value - metric.previous) / Math.abs(metric.previous)) * 100) || 0;
    const good = metric.higher_is_better ? rounded > 0 : rounded < 0;
    return { text: `${rounded > 0 ? "+" : ""}${number.format(rounded)}%`, good, flat: rounded === 0 };
  };
  const day = (value: string) => formatDay(value, locale, { day: "numeric", month: "short" });
  const atRisk = data?.atRisk ?? [];
  const shownAtRisk = allAtRisk ? atRisk : atRisk.slice(0, AT_RISK_SHOWN);
  const trendUnit = trend === "revenue" ? "money" : "count";

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <View style={{ gap: 4 }}>
        <Heading palette={palette}>{t("title")}</Heading>
        <Text style={[styles.muted, { color: palette.muted }]}>
          {branch ? t("periodBranch", { count: Number(days), branch: branch.name }) : t("period", { count: Number(days) })}
        </Text>
      </View>
      <PillRow
        label={tReports("period")}
        palette={palette}
        value={days}
        onChange={setDays}
        options={(["7", "30", "90"] as const).map((value) => ({ value, label: t("days", { count: Number(value) }) }))}
      />

      {data && metrics.length === 0 ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("empty")}</Text>
        </Card>
      ) : (
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 10 }}>
          {metrics.map((metric) => {
            const delta = change(metric);
            const label = tMetrics(metric.key);
            const value = show(metric.unit, metric.value);
            return (
              <View
                key={metric.key}
                accessible
                accessibilityLabel={[label, value, delta && t("vsBefore", { change: delta.text })].filter(Boolean).join(", ")}
                style={{
                  flexGrow: 1,
                  flexBasis: "45%",
                  borderWidth: 1,
                  borderRadius: 16,
                  padding: 14,
                  gap: 4,
                  backgroundColor: palette.surface,
                  borderColor: palette.border,
                }}
              >
                <Text style={{ color: palette.muted, fontSize: 13, fontWeight: "600", textAlign: "left" }}>{label}</Text>
                <Text
                  style={{ color: palette.foreground, fontSize: 22, fontWeight: "700", textAlign: "left", fontVariant: ["tabular-nums"] }}
                >
                  {value}
                </Text>
                {delta && (
                  <Text
                    style={{
                      color: delta.flat ? palette.muted : delta.good ? palette.success : palette.danger,
                      fontSize: 13,
                      fontWeight: "600",
                      textAlign: "left",
                    }}
                  >
                    {t("vsBefore", { change: delta.text })}
                  </Text>
                )}
              </View>
            );
          })}
        </View>
      )}

      <SectionTitle title={t("trend")} palette={palette} />
      <PillRow
        label={t("trend")}
        palette={palette}
        value={trend}
        onChange={setTrend}
        options={(["revenue", "attendance"] as const).map((value) => ({ value, label: tMetrics(value) }))}
      />
      <Bars
        points={points ?? []}
        label={(bucket) => (days === "90" ? t("weekOf", { date: day(bucket) }) : day(bucket))}
        value={(value) => show(trendUnit, value)}
        empty={t("noTrend")}
        palette={palette}
      />

      <SectionTitle title={tReports("byService")} palette={palette} />
      {data && data.services.length === 0 && (
        <Text style={[styles.muted, { color: palette.muted }]}>{tReports("noSessions")}</Text>
      )}
      {data?.services.map((row) => (
        <ListRow
          key={row.key}
          palette={palette}
          title={row.label ?? "—"}
          subtitle={t("breakdownLine", {
            sessions: row.sessions,
            attended: row.attended,
            occupancy: percent(row.occupancy),
          })}
        />
      ))}

      {byBranch && (
        <>
          <SectionTitle title={tReports("byBranch")} palette={palette} />
          {data?.branchRows.map((row) => (
            <ListRow
              key={row.key}
              palette={palette}
              title={row.label || tReports("noBranch")}
              subtitle={t("breakdownLine", {
                sessions: row.sessions,
                attended: row.attended,
                occupancy: percent(row.occupancy),
              })}
            />
          ))}
        </>
      )}

      <SectionTitle
        title={tReports("atRisk", { count: atRisk.length })}
        action={!allAtRisk && atRisk.length > AT_RISK_SHOWN ? tReports("showAll", { count: atRisk.length }) : undefined}
        onAction={() => setAllAtRisk(true)}
        palette={palette}
      />
      <Text style={[styles.muted, { color: palette.muted }]}>{tReports("atRiskHint", { days: AT_RISK_DAYS })}</Text>
      {data && atRisk.length === 0 && (
        <Card palette={palette}>
          <Text style={{ color: palette.foreground }}>{tReports("atRiskNone")}</Text>
        </Card>
      )}
      {shownAtRisk.map((member) => (
        <ListRow
          key={member.client_id}
          palette={palette}
          title={member.name}
          subtitle={[
            member.last_visit ? tReports("lastVisit", { date: day(member.last_visit) }) : tReports("neverVisited"),
            member.plan_ends_on && tReports("planEnds", { date: day(member.plan_ends_on) }),
          ]
            .filter(Boolean)
            .join(" · ")}
          trailing={
            <Badge
              palette={palette}
              tone={member.reason === "plan_ending" ? "danger" : "muted"}
              label={tReports(`reasons.${member.reason}`)}
            />
          }
          onPress={() => router.push(`/client/${member.client_id}`)}
        />
      ))}
    </Screen>
  );
}

/** A simple bar chart: one bar per day or week, the tallest one full height. Each bar reads its
 * date and value to a screen reader; the best one is named below the chart. */
function Bars({
  points,
  label,
  value,
  empty,
  palette,
}: {
  points: { bucket: string; value: number }[];
  label: (bucket: string) => string;
  value: (value: number) => string;
  empty: string;
  palette: Palette;
}) {
  const t = useTranslations("business.numbers");
  const max = Math.max(0, ...points.map((point) => point.value));
  if (points.length === 0 || max === 0) {
    return <Text style={[styles.muted, { color: palette.muted }]}>{empty}</Text>;
  }
  const best = points.reduce((top, point) => (point.value > top.value ? point : top));
  return (
    <View style={{ gap: 8 }}>
      <View
        style={{
          flexDirection: "row",
          alignItems: "flex-end",
          gap: points.length > 20 ? 2 : 4,
          height: 120,
          borderBottomWidth: 1,
          borderColor: palette.border,
        }}
      >
        {points.map((point) => (
          <View
            key={point.bucket}
            accessible
            accessibilityLabel={`${label(point.bucket)}: ${value(point.value)}`}
            style={{
              flex: 1,
              height: `${Math.max(2, (point.value / max) * 100)}%`,
              backgroundColor: point === best ? palette.primary : palette.border,
              borderTopLeftRadius: 4,
              borderTopRightRadius: 4,
            }}
          />
        ))}
      </View>
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <Text style={{ color: palette.muted, fontSize: 12 }}>{label(points[0].bucket)}</Text>
        <Text style={{ color: palette.muted, fontSize: 12 }}>{label(points[points.length - 1].bucket)}</Text>
      </View>
      <Text style={{ color: palette.foreground, textAlign: "left" }}>
        {t("best", { when: label(best.bucket), value: value(best.value) })}
      </Text>
    </View>
  );
}
