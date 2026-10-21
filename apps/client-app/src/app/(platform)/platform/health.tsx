import { router, useFocusEffect } from "expo-router";
import { useCallback } from "react";
import { View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { BackBar, Badge, ListRow, SectionTitle, StatTile, TileGrid } from "@business-os/app-kit/components/rows";
import { Card, EmptyState, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { usePlatform } from "@/providers/platform-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

/** System health on the phone: the background jobs, the queues, AI spend today and the latest
 * crashes. It reads the same numbers as the console page. */
export default function Health() {
  const t = useTranslations("platform.health");
  const tApp = useTranslations("staffApp.health");
  const locale = useLocale();
  const { api, can } = usePlatform();
  const { palette } = useTheme();
  const allowed = can("usage.read");

  const load = useCallback(async () => (allowed ? unwrap(await api.GET("/platform/health")) : null), [api, allowed]);
  const { data: health, loading, reload } = useLoad(load);
  useFocusEffect(
    useCallback(() => {
      void reload();
    }, [reload]),
  );

  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "short", timeStyle: "short" });
  const back = <BackBar label={tApp("back")} palette={palette} onPress={() => router.back()} />;

  if (!allowed) {
    return (
      <Screen palette={palette}>
        {back}
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{tApp("noPermission")}</Text>
        </Card>
      </Screen>
    );
  }

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      {back}
      <Heading palette={palette}>{t("title")}</Heading>
      {health && (
        <>
          <TileGrid>
            <StatTile palette={palette} label={t("messagesQueued")} value={number.format(health.messages_queued)} />
            <StatTile palette={palette} label={t("messagesFailed")} value={number.format(health.messages_failed_24h)} />
            <StatTile palette={palette} label={t("emailsWaiting")} value={number.format(health.emails_waiting)} />
            <StatTile palette={palette} label={t("database")} value={`${number.format(health.database_bytes / (1024 * 1024))} MB`} />
            <StatTile
              palette={palette}
              label={t("aiToday")}
              value={`${number.format(health.ai_credits_today)} ${t("aiLimit", { limit: number.format(health.ai_alert_at) })}`}
            />
          </TileGrid>

          <View style={{ gap: 8 }}>
            <SectionTitle title={t("jobs")} palette={palette} />
            {health.jobs.length === 0 ? (
              <EmptyState palette={palette} message={t("noJobs")} icon="pulse-outline" />
            ) : (
              health.jobs.map((job) => {
                const state = job.late ? "late" : job.last_ok === false ? "failed" : "ok";
                return (
                  <ListRow
                    key={job.job}
                    palette={palette}
                    title={job.job}
                    subtitle={`${t("lastOk")}: ${job.last_ok_at ? when.format(new Date(job.last_ok_at)) : t("never")}`}
                    trailing={<Badge label={t(state)} tone={state === "ok" ? "success" : "danger"} palette={palette} />}
                  />
                );
              })
            )}
          </View>

          <View style={{ gap: 8 }}>
            <SectionTitle title={t("errors")} palette={palette} />
            {health.errors.length === 0 ? (
              <EmptyState palette={palette} message={t("noErrors")} icon="pulse-outline" />
            ) : (
              health.errors.slice(0, 10).map((error, index) => (
                <ListRow
                  key={`${error.at}-${index}`}
                  palette={palette}
                  title={`${error.method} ${error.path ?? ""}`.trim()}
                  subtitle={`${when.format(new Date(error.at))} · ${error.status}${error.error ? ` · ${error.error}` : ""}`}
                />
              ))
            )}
          </View>
        </>
      )}
    </Screen>
  );
}
