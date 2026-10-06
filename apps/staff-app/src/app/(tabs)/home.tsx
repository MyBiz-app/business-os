import { router, useFocusEffect } from "expo-router";
import { useCallback } from "react";
import { Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Avatar, Badge, ListRow, SectionTitle, StatTile, TileGrid } from "@business-os/app-kit/components/rows";
import { Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { formatMoney } from "@business-os/app-kit/lib/money";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { industryName } from "@business-os/app-kit/lib/vertical";
import { useStaff } from "@/providers/staff-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

const WEEK = 7 * 24 * 60 * 60 * 1000;
const SHOWN = 5;

/** What needs attention right now: open requests, the businesses that just joined, the platform's
 * numbers and this month's billing. Each part appears only for someone allowed to see it. */
export default function Home() {
  const t = useTranslations("staffApp.home");
  const tLevels = useTranslations("platform.levels");
  const tStatus = useTranslations("platform.inbox.statuses");
  const tRoot = useTranslations();
  const locale = useLocale();
  const { api, staff, can } = useStaff();
  const { palette } = useTheme();

  const load = useCallback(async () => {
    const [requests, businesses, billing] = await Promise.all([
      can("inbox.manage") ? api.GET("/platform/contact-requests").then(unwrap) : [],
      can("businesses.read") ? api.GET("/platform/businesses").then(unwrap) : [],
      can("billing.manage") ? api.GET("/platform/billing").then(unwrap) : [],
    ]);
    return { requests, businesses, billing };
  }, [api, can]);
  const { data, loading, reload } = useLoad(load);
  useFocusEffect(
    useCallback(() => {
      void reload();
    }, [reload]),
  );

  const open = (data?.requests ?? []).filter((r) => r.status !== "done");
  const since = Date.now() - WEEK;
  const businesses = data?.businesses ?? [];
  const fresh = businesses.filter((b) => new Date(b.created_at).getTime() > since);
  const month = [...(data?.billing ?? [])].sort((a, b) => b.month.localeCompare(a.month))[0];
  const number = new Intl.NumberFormat(locale);
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium" });

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <View style={{ gap: 4 }}>
        <Heading palette={palette}>{t("title")}</Heading>
        {staff && <Text style={[styles.muted, { color: palette.muted }]}>{t("youAre", { level: tLevels(staff.level) })}</Text>}
      </View>

      <TileGrid>
        {can("inbox.manage") && <StatTile palette={palette} label={t("open")} value={number.format(open.length)} />}
        {can("businesses.read") && (
          <StatTile palette={palette} label={t("newBusinesses")} value={number.format(fresh.length)} />
        )}
        {can("businesses.read") && <StatTile palette={palette} label={t("businesses")} value={number.format(businesses.length)} />}
        {can("businesses.read") && (
          <StatTile
            palette={palette}
            label={t("activeClients")}
            value={number.format(businesses.reduce((sum, b) => sum + b.active_clients, 0))}
          />
        )}
      </TileGrid>

      {month && (
        <Card palette={palette}>
          <Text style={{ color: palette.muted, fontSize: 14, fontWeight: "600", textAlign: "left" }}>
            {t("billing", {
              month: new Intl.DateTimeFormat(locale, { month: "long", year: "numeric", timeZone: "UTC" }).format(
                new Date(`${month.month}T12:00:00Z`),
              ),
            })}
          </Text>
          <Text style={{ color: palette.foreground, fontSize: 24, fontWeight: "700", textAlign: "left" }}>
            {formatMoney(month.paid + month.open, month.currency, locale)}
          </Text>
          <Text style={[styles.muted, { color: palette.muted }]}>
            {t("paidOpen", {
              paid: formatMoney(month.paid, month.currency, locale),
              open: formatMoney(month.open, month.currency, locale),
            })}
          </Text>
        </Card>
      )}

      {open.length === 0 && fresh.length === 0 && !loading ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("nothing")}</Text>
        </Card>
      ) : null}

      {open.length > 0 && (
        <View style={{ gap: 8 }}>
          <SectionTitle title={t("latest")} palette={palette} />
          {open.slice(0, SHOWN).map((request) => (
            <ListRow
              key={request.id}
              palette={palette}
              leading={<Avatar name={request.name} palette={palette} size={36} />}
              title={request.name}
              subtitle={[date.format(new Date(request.created_at)), request.message].filter(Boolean).join(" · ")}
              trailing={<Badge label={tStatus(request.status)} tone={request.status === "new" ? "danger" : "primary"} palette={palette} />}
              onPress={() => router.push(`/request/${request.id}`)}
            />
          ))}
        </View>
      )}

      {fresh.length > 0 && (
        <View style={{ gap: 8 }}>
          <SectionTitle title={t("newest")} palette={palette} />
          {fresh.slice(0, SHOWN).map((business) => (
            <ListRow
              key={business.id}
              palette={palette}
              leading={<Avatar name={business.name} palette={palette} size={36} />}
              title={business.name}
              subtitle={`${industryName(tRoot, business.vertical)} · ${date.format(new Date(business.created_at))}`}
              onPress={() => router.push(`/business/${business.id}`)}
            />
          ))}
        </View>
      )}
    </Screen>
  );
}
