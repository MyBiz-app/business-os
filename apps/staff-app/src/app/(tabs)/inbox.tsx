import { useCallback, useState } from "react";
import { Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { SegmentedControl } from "@business-os/app-kit/components/segmented-control";
import { Button, Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
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
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!can("inbox.manage")) return [];
    return unwrap(await api.GET("/platform/contact-requests"));
  }, [api, can]);
  const { data, loading, reload } = useLoad(load);

  const move = async (id: string, update: { status?: "in_progress" | "done"; assignee?: string }) => {
    setBusy(id);
    try {
      unwrap(
        await api.PATCH("/platform/contact-requests/{request_id}", {
          params: { path: { request_id: id } },
          body: update,
        }),
      );
      await reload();
    } finally {
      setBusy(null);
    }
  };

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
        requests.slice(0, 50).map((request) => (
          <Card key={request.id} palette={palette}>
            <View style={{ gap: 2 }}>
              <Text style={{ color: palette.foreground, fontWeight: "600" }}>
                {request.name}
                {request.business ? ` · ${request.business}` : ""}
              </Text>
              <Text style={{ color: palette.muted, fontSize: 13 }}>
                {when.format(new Date(request.created_at))} · {tStatus(request.status)}
                {request.from_business ? ` · ${t("fromBusiness")}` : ""}
              </Text>
              <Text style={{ color: palette.muted, fontSize: 13, writingDirection: "ltr" }}>{request.email}</Text>
              {request.message && <Text style={{ color: palette.foreground }}>{request.message}</Text>}
              {request.assignee && (
                <Text style={{ color: palette.muted, fontSize: 13, writingDirection: "ltr" }}>{request.assignee}</Text>
              )}
            </View>
            <View style={{ flexDirection: "row", gap: 8 }}>
              {!request.assignee && request.status !== "done" && (
                <View style={{ flex: 1 }}>
                  <Button
                    label={t("take")}
                    variant="secondary"
                    palette={palette}
                    busy={busy === request.id}
                    onPress={() => void move(request.id, { assignee: "me", status: "in_progress" })}
                  />
                </View>
              )}
              {request.status !== "done" && (
                <View style={{ flex: 1 }}>
                  <Button
                    label={t("markDone")}
                    palette={palette}
                    busy={busy === request.id}
                    onPress={() => void move(request.id, { status: "done" })}
                  />
                </View>
              )}
            </View>
          </Card>
        ))
      )}
    </Screen>
  );
}
