import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useState } from "react";
import { Linking, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Avatar, BackBar, Badge, ListRow, PillRow, SectionTitle, StatTile, TileGrid } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { formatMoney } from "@business-os/app-kit/lib/money";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { industryName } from "@business-os/app-kit/lib/vertical";
import { useStaff } from "@/providers/staff-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

type Days = "7" | "14" | "30";

/** One business, for the MyBiz team: who owns it, how it's used, its modules and invoices, and
 * (with billing rights) more trial days. Actions are logged for the business's owner to see. */
export default function BusinessScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const t = useTranslations("staffApp.business");
  const tBusinesses = useTranslations("staffApp.businesses");
  const tHome = useTranslations("staffApp.home");
  const tColumns = useTranslations("platform.columns");
  const tActions = useTranslations("platform.actions");
  const tModules = useTranslations("modules.names");
  const tRoot = useTranslations();
  const locale = useLocale();
  const { api, can } = useStaff();
  const { palette } = useTheme();
  const [days, setDays] = useState<Days>("14");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const billing = can("billing.manage");

  const load = useCallback(async () => {
    const [all, invoices] = await Promise.all([
      api.GET("/platform/businesses").then(unwrap),
      billing
        ? api.GET("/platform/businesses/{tenant_id}/invoices", { params: { path: { tenant_id: id } } }).then(unwrap)
        : Promise.resolve([]),
    ]);
    return { business: all.find((b) => b.id === id) ?? null, invoices };
  }, [api, id, billing]);
  const { data, loading, reload } = useLoad(load);

  const date = (value: string, options: Intl.DateTimeFormatOptions = { dateStyle: "medium" }) =>
    new Intl.DateTimeFormat(locale, { ...options, timeZone: "UTC" }).format(new Date(value.length === 10 ? `${value}T12:00:00Z` : value));
  const number = new Intl.NumberFormat(locale);

  const extend = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const trial = unwrap(
        await api.POST("/platform/businesses/{tenant_id}/trial", { params: { path: { tenant_id: id } }, body: { days: Number(days) } }),
      );
      setNotice(tActions("trialDone", { date: date(trial.trial_ends_at) }));
    } catch {
      setError(tActions("errors.generic"));
    } finally {
      setBusy(false);
    }
  };

  const business = data?.business;
  if (!business) {
    return (
      <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
        <BackBar label={tBusinesses("back")} palette={palette} onPress={() => router.back()} />
        {data && <Text style={[styles.muted, { color: palette.muted }]}>{tBusinesses("none")}</Text>}
      </Screen>
    );
  }

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <BackBar label={tBusinesses("back")} palette={palette} onPress={() => router.back()} />
      <View style={{ flexDirection: "row", alignItems: "center", gap: 14 }}>
        <Avatar name={business.name} palette={palette} size={56} />
        <View style={{ flex: 1, gap: 4 }}>
          <Heading palette={palette}>{business.name}</Heading>
          <Text style={[styles.muted, { color: palette.muted }]}>
            {industryName(tRoot, business.vertical)} · {t("since", { date: date(business.created_at) })}
          </Text>
        </View>
      </View>

      {business.owner_email && (
        <ListRow
          palette={palette}
          title={business.owner_email}
          subtitle={tColumns("owner")}
          accessibilityLabel={t("emailOwner")}
          onPress={() => void Linking.openURL(`mailto:${business.owner_email}`)}
        />
      )}

      <SectionTitle title={t("numbers")} palette={palette} />
      <TileGrid>
        <StatTile palette={palette} label={tColumns("clients")} value={number.format(business.clients)} />
        <StatTile palette={palette} label={tHome("activeClients")} value={number.format(business.active_clients)} />
        <StatTile palette={palette} label={tHome("bookings")} value={number.format(business.bookings_30d)} />
        <StatTile palette={palette} label={tColumns("members")} value={number.format(business.members)} />
        <StatTile palette={palette} label={tColumns("aiCredits30d")} value={number.format(business.ai_credits_30d)} />
      </TileGrid>

      <Card palette={palette}>
        <SectionTitle title={tColumns("modules")} palette={palette} />
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
          {business.modules.length === 0 ? (
            <Badge label={t("noModules")} palette={palette} />
          ) : (
            business.modules.map((key) => <Badge key={key} label={tModules(key as "client_app")} tone="primary" palette={palette} />)
          )}
        </View>
      </Card>

      <View accessibilityLiveRegion="polite">
        {notice ? <Text style={{ color: palette.success, fontWeight: "600" }}>{notice}</Text> : null}
        <ErrorText message={error} palette={palette} />
      </View>

      {billing && (
        <Card palette={palette}>
          <SectionTitle title={tActions("trial")} palette={palette} />
          <Text style={[styles.muted, { color: palette.muted }]}>{tActions("intro")}</Text>
          <PillRow<Days>
            label={tActions("trialDays")}
            palette={palette}
            value={days}
            onChange={setDays}
            options={(["7", "14", "30"] as Days[]).map((value) => ({ value, label: value, sublabel: tActions("trialDays") }))}
          />
          <Button label={t("extend", { days })} palette={palette} busy={busy} onPress={() => void extend()} />
        </Card>
      )}

      {billing && (
        <View style={{ gap: 8 }}>
          <SectionTitle title={tRoot("platform.invoices")} palette={palette} />
          {(data?.invoices ?? []).length === 0 ? (
            <Text style={[styles.muted, { color: palette.muted }]}>{tActions("noInvoices")}</Text>
          ) : (
            (data?.invoices ?? []).map((invoice) => (
              <ListRow
                key={invoice.id}
                palette={palette}
                title={tActions("invoice", {
                  number: invoice.number,
                  amount: formatMoney(invoice.total, invoice.currency, locale),
                })}
                subtitle={t("period", {
                  from: date(invoice.period_start, { day: "numeric", month: "short" }),
                  to: date(invoice.period_end, { day: "numeric", month: "short", year: "numeric" }),
                })}
                trailing={
                  <Badge
                    label={t(`statuses.${invoice.status}`)}
                    tone={invoice.status === "paid" ? "success" : invoice.status === "open" ? "danger" : "muted"}
                    palette={palette}
                  />
                }
              />
            ))
          )}
        </View>
      )}
    </Screen>
  );
}
