import { formatDay } from "@business-os/i18n/dates";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback } from "react";
import { Linking, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Button, Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

/** One client: how to reach them, their plans and their last visits. */
export default function ClientScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const t = useTranslations("business.clients");
  const locale = useLocale();
  const { api, scope, tenant, palette } = useBusiness();

  const load = useCallback(async () => {
    const [client, bookings, entitlements] = await Promise.all([
      api.GET("/clients/{client_id}", { params: { ...scope, path: { client_id: id } } }).then(unwrap),
      api.GET("/clients/{client_id}/bookings", { params: { ...scope, path: { client_id: id } } }).then(unwrap),
      api
        .GET("/clients/{client_id}/entitlements", { params: { ...scope, path: { client_id: id } } })
        .then(unwrap)
        .catch(() => []),
    ]);
    return { client, bookings, entitlements };
  }, [api, scope, id]);
  const { data, loading, reload } = useLoad(load);
  if (!data || !tenant) {
    return (
      <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
        <View />
      </Screen>
    );
  }

  const { client, bookings, entitlements } = data;
  const name = [client.first_name, client.last_name].filter(Boolean).join(" ");
  const visits = bookings.filter((b) => b.status === "checked_in");
  const last = visits[0]?.starts_at;
  const active = entitlements.filter((e) => e.state === "active");
  const digits = client.phone?.replace(/\D/g, "");

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <Button label={t("search")} variant="secondary" palette={palette} onPress={() => router.back()} />
      <View style={{ gap: 4 }}>
        <Heading palette={palette}>{name}</Heading>
        <Text style={[styles.muted, { color: palette.muted }]}>
          {t("visits", { count: visits.length })}
          {" · "}
          {last
            ? t("lastVisit", { date: formatDay(last.slice(0, 10), locale, { day: "numeric", month: "short" }) })
            : t("neverVisited")}
        </Text>
      </View>

      {(client.phone || client.email) && (
        <View style={{ flexDirection: "row", gap: 8 }}>
          {client.phone && (
            <>
              <View style={{ flex: 1 }}>
                <Button label={t("call")} palette={palette} onPress={() => void Linking.openURL(`tel:${client.phone}`)} />
              </View>
              <View style={{ flex: 1 }}>
                <Button
                  label={t("whatsapp")}
                  variant="secondary"
                  palette={palette}
                  onPress={() => void Linking.openURL(`https://wa.me/${digits}`)}
                />
              </View>
            </>
          )}
          {client.email && !client.phone && (
            <View style={{ flex: 1 }}>
              <Button
                label={t("email")}
                variant="secondary"
                palette={palette}
                onPress={() => void Linking.openURL(`mailto:${client.email}`)}
              />
            </View>
          )}
        </View>
      )}

      <Card palette={palette}>
        <Text style={{ color: palette.foreground, fontWeight: "600" }}>{t("plan")}</Text>
        {active.length === 0 ? (
          <Text style={[styles.muted, { color: palette.muted }]}>{t("noPlan")}</Text>
        ) : (
          active.map((plan) => (
            <Text key={plan.id} style={[styles.muted, { color: palette.muted }]}>
              {plan.name} · {formatDay(plan.ends_on, locale, { day: "numeric", month: "short" })}
            </Text>
          ))
        )}
      </Card>

      {client.notes && (
        <Card palette={palette}>
          <Text style={{ color: palette.foreground, fontWeight: "600" }}>{t("notes")}</Text>
          <Text style={[styles.muted, { color: palette.muted }]}>{client.notes}</Text>
        </Card>
      )}
    </Screen>
  );
}
