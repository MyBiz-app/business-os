import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { SegmentedControl } from "@business-os/app-kit/components/segmented-control";
import { Avatar, Badge, ListRow } from "@business-os/app-kit/components/rows";
import { Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useStaff } from "@/providers/staff-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

/** Requests from the website and messages from businesses, handled on the go. */
export default function Inbox() {
  const t = useTranslations("staffApp.inbox");
  const tStatus = useTranslations("platform.inbox.statuses");
  const locale = useLocale();
  const { api, can } = useStaff();
  const { palette } = useTheme();
  const [filter, setFilter] = useState<"open" | "done">("open");

  const load = useCallback(async () => {
    if (!can("inbox.manage")) return [];
    return unwrap(await api.GET("/platform/contact-requests"));
  }, [api, can]);
  const { data, loading, reload } = useLoad(load);
  // Coming back from a request shows its new status.
  useFocusEffect(
    useCallback(() => {
      void reload();
    }, [reload]),
  );

  const when = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });
  const requests = (data ?? []).filter((r) => (filter === "done" ? r.status === "done" : r.status !== "done"));

  if (!can("inbox.manage")) {
    return (
      <Screen palette={palette}>
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("noPermission")}</Text>
        </Card>
      </Screen>
    );
  }

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <Heading palette={palette}>{t("title")}</Heading>
      <SegmentedControl
        label={t("title")}
        value={filter}
        options={[
          { value: "open" as const, label: t("open") },
          { value: "done" as const, label: t("done") },
        ]}
        onChange={setFilter}
      />
      {requests.length === 0 ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("empty")}</Text>
        </Card>
      ) : (
        <View style={{ gap: 8 }}>
          {requests.slice(0, 50).map((request) => (
            <ListRow
              key={request.id}
              palette={palette}
              leading={<Avatar name={request.name} palette={palette} />}
              title={request.business ? `${request.name} · ${request.business}` : request.name}
              subtitle={[when.format(new Date(request.created_at)), request.from_business ? t("fromBusiness") : null, request.message]
                .filter(Boolean)
                .join(" · ")}
              trailing={
                <Badge
                  label={tStatus(request.status)}
                  tone={request.status === "new" ? "danger" : request.status === "done" ? "success" : "primary"}
                  palette={palette}
                />
              }
              onPress={() => router.push(`/request/${request.id}`)}
            />
          ))}
        </View>
      )}
    </Screen>
  );
}
