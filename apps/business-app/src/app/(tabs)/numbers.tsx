import { addDays, todayIn } from "@business-os/i18n/dates";
import { useCallback } from "react";
import { Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { formatMoney } from "@business-os/app-kit/lib/money";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

const DAYS = 30;
const KEYS = ["revenue", "active_clients", "attendance", "occupancy", "no_show_rate", "new_clients"] as const;

/** The key numbers the owner checks between clients. */
export default function Numbers() {
  const t = useTranslations("business.numbers");
  const tMetrics = useTranslations("metrics");
  const locale = useLocale();
  const { api, scope, tenant, palette } = useBusiness();
  const timeZone = tenant?.time_zone ?? "UTC";

  const load = useCallback(async () => {
    const end = addDays(todayIn(timeZone), -1);
    const start = addDays(end, -(DAYS - 1));
    return unwrap(await api.GET("/metrics", { params: { ...scope, query: { start, end, keys: [...KEYS] } } }));
  }, [api, scope, timeZone]);
  const { data, loading, reload } = useLoad(load);
  if (!tenant) return null;

  const number = new Intl.NumberFormat(locale);
  const show = (metric: (typeof metrics)[number]) => {
    if (metric.value === null) return "—";
    if (metric.unit === "money") return formatMoney(Math.round(metric.value), tenant.currency, locale);
    if (metric.unit === "percent") return `${number.format(Math.round(metric.value))}%`;
    return number.format(metric.value);
  };
  const metrics = data ?? [];
  const change = (metric: (typeof metrics)[number]) => {
    if (metric.value === null || metric.previous === null || metric.previous === 0) return null;
    const delta = ((metric.value - metric.previous) / Math.abs(metric.previous)) * 100;
    const rounded = Math.round(delta) || 0;
    const good = metric.higher_is_better ? rounded > 0 : rounded < 0;
    return { text: `${rounded > 0 ? "+" : ""}${number.format(rounded)}%`, good };
  };

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <View style={{ gap: 4 }}>
        <Heading palette={palette}>{t("title")}</Heading>
        <Text style={[styles.muted, { color: palette.muted }]}>{t("period", { count: DAYS })}</Text>
      </View>
      {metrics.length === 0 ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("empty")}</Text>
        </Card>
      ) : (
        metrics.map((metric) => {
          const delta = change(metric);
          return (
            <Card key={metric.key} palette={palette}>
              <Text style={{ color: palette.muted, fontSize: 14 }}>{tMetrics(metric.key)}</Text>
              <View style={{ flexDirection: "row", alignItems: "baseline", gap: 10 }}>
                <Text style={{ color: palette.foreground, fontSize: 28, fontWeight: "700" }}>{show(metric)}</Text>
                {delta && (
                  <Text style={{ color: delta.good ? palette.success : palette.danger, fontWeight: "600" }}>
                    {delta.text}
                  </Text>
                )}
              </View>
            </Card>
          );
        })
      )}
    </Screen>
  );
}
