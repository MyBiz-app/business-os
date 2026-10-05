import type { components } from "@business-os/api-client";
import { formatTime } from "@business-os/i18n/dates";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useState } from "react";
import { Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Button, Card, ErrorText, Heading, Screen, styles } from "@/components/ui";
import { unwrap } from "@/lib/api";
import { useLoad } from "@/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Booking = components["schemas"]["Booking"];

const TONE = { checked_in: "success", no_show: "danger", cancelled: "muted" } as const;

/** One session: who's coming, and check-in for the front desk. */
export default function SessionScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const t = useTranslations("business.today");
  const locale = useLocale();
  const { api, scope, tenant, palette, can } = useBusiness();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timeZone = tenant?.time_zone ?? "UTC";

  const load = useCallback(async () => {
    const [sessions, bookings] = await Promise.all([
      api.GET("/sessions/{session_id}", { params: { ...scope, path: { session_id: id } } }).then(unwrap),
      api.GET("/sessions/{session_id}/bookings", { params: { ...scope, path: { session_id: id } } }).then(unwrap),
    ]);
    return { session: sessions, bookings };
  }, [api, scope, id]);
  const { data, loading, reload } = useLoad(load);

  const setStatus = async (booking: Booking, status: "checked_in" | "no_show" | "booked") => {
    setBusy(booking.id);
    setError(null);
    try {
      unwrap(
        await api.PATCH("/bookings/{booking_id}", {
          params: { ...scope, path: { booking_id: booking.id } },
          body: { status },
        }),
      );
      await reload();
    } catch {
      setError(t("saved"));
    } finally {
      setBusy(null);
    }
  };

  if (!data) {
    return (
      <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
        <Button label={t("openSchedule")} variant="secondary" palette={palette} onPress={() => router.back()} />
      </Screen>
    );
  }
  const { session, bookings } = data;
  const coming = bookings.filter((b) => b.status !== "cancelled");

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <Button label={t("openSchedule")} variant="secondary" palette={palette} onPress={() => router.back()} />
      <View style={{ gap: 4 }}>
        <Heading palette={palette}>{session.service.name}</Heading>
        <Text style={[styles.muted, { color: palette.muted }]}>
          {formatTime(session.starts_at, locale, timeZone)}–{formatTime(session.ends_at, locale, timeZone)} ·{" "}
          {t("spots", { booked: session.booked, capacity: session.capacity })}
        </Text>
      </View>

      <Heading palette={palette} level={2}>
        {t("roster")}
      </Heading>
      <ErrorText message={error} palette={palette} />
      {coming.length === 0 ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("empty")}</Text>
        </Card>
      ) : (
        coming.map((booking) => {
          const tone = TONE[booking.status as keyof typeof TONE];
          return (
            <Card key={booking.id} palette={palette}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
                <View style={{ flex: 1, gap: 2 }}>
                  <Text style={{ color: palette.foreground, fontWeight: "600" }}>{booking.client_name}</Text>
                  <Text
                    style={{
                      color: tone === "success" ? palette.success : tone === "danger" ? palette.danger : palette.muted,
                      fontSize: 13,
                    }}
                  >
                    {t(`statuses.${booking.status}`)}
                    {booking.plan_name ? ` · ${booking.plan_name}` : ""}
                  </Text>
                </View>
              </View>
              {can("bookings.manage") && booking.status !== "waitlisted" && (
                <View style={{ flexDirection: "row", gap: 8 }}>
                  {booking.status === "checked_in" ? (
                    <View style={{ flex: 1 }}>
                      <Button
                        label={t("undo")}
                        variant="secondary"
                        palette={palette}
                        busy={busy === booking.id}
                        onPress={() => void setStatus(booking, "booked")}
                      />
                    </View>
                  ) : (
                    <>
                      <View style={{ flex: 1 }}>
                        <Button
                          label={t("checkIn")}
                          palette={palette}
                          busy={busy === booking.id}
                          onPress={() => void setStatus(booking, "checked_in")}
                        />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Button
                          label={t("noShow")}
                          variant="secondary"
                          palette={palette}
                          busy={busy === booking.id}
                          onPress={() => void setStatus(booking, "no_show")}
                        />
                      </View>
                    </>
                  )}
                </View>
              )}
            </Card>
          );
        })
      )}
    </Screen>
  );
}
