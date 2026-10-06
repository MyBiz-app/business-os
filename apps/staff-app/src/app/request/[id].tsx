import type { components } from "@business-os/api-client";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useState } from "react";
import { Linking, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Avatar, BackBar, Badge, PillRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { industryName } from "@business-os/app-kit/lib/vertical";
import { useStaff } from "@/providers/staff-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

type Status = components["schemas"]["ContactRequest"]["status"];
type Update = components["schemas"]["InboxUpdate"];

/** One request: who wrote and what, reaching them, its status, who handles it and internal notes. */
export default function RequestScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const t = useTranslations("staffApp.request");
  const tInbox = useTranslations("platform.inbox");
  const tRoot = useTranslations();
  const locale = useLocale();
  const { api, can, staff } = useStaff();
  const { palette } = useTheme();
  const [notes, setNotes] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const all = unwrap(await api.GET("/platform/contact-requests"));
    return all.find((r) => r.id === id) ?? null;
  }, [api, id]);
  const { data: request, loading, reload } = useLoad(load);

  const update = async (body: Update, done: string) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      unwrap(await api.PATCH("/platform/contact-requests/{request_id}", { params: { path: { request_id: id } }, body }));
      setNotice(done);
      await reload();
    } catch {
      setError(t("error"));
    } finally {
      setBusy(false);
    }
  };

  if (!request) {
    return (
      <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
        <BackBar label={t("back")} palette={palette} onPress={() => router.back()} />
        {request === null && <Text style={[styles.muted, { color: palette.muted }]}>{tInbox("empty")}</Text>}
      </Screen>
    );
  }

  const mine = request.assignee === staff?.email;
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(new Date(request.created_at));
  const digits = request.phone?.replace(/\D/g, "");

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <BackBar label={t("back")} palette={palette} onPress={() => router.back()} />
      <View style={{ flexDirection: "row", alignItems: "center", gap: 14 }}>
        <Avatar name={request.name} palette={palette} size={56} />
        <View style={{ flex: 1, gap: 4 }}>
          <Heading palette={palette}>{request.name}</Heading>
          <View style={{ flexDirection: "row", gap: 6, flexWrap: "wrap" }}>
            <Badge
              label={tInbox(`statuses.${request.status}`)}
              tone={request.status === "new" ? "danger" : request.status === "done" ? "success" : "primary"}
              palette={palette}
            />
            <Badge label={request.from_business ? tInbox("fromBusiness") : tInbox("fromSite")} palette={palette} />
          </View>
        </View>
      </View>
      <Text style={[styles.muted, { color: palette.muted }]}>
        {[when, request.business, request.vertical ? industryName(tRoot, request.vertical) : null].filter(Boolean).join(" · ")}
      </Text>

      {request.message ? (
        <Card palette={palette}>
          <Text style={{ color: palette.foreground, fontSize: 16, textAlign: "left" }}>{request.message}</Text>
        </Card>
      ) : null}

      <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
        {request.phone && (
          <View style={{ flexGrow: 1, flexBasis: "30%" }}>
            <Button label={t("call")} palette={palette} onPress={() => void Linking.openURL(`tel:${request.phone}`)} />
          </View>
        )}
        {request.phone && (
          <View style={{ flexGrow: 1, flexBasis: "30%" }}>
            <Button
              label="WhatsApp"
              variant="secondary"
              palette={palette}
              onPress={() => void Linking.openURL(`https://wa.me/${digits}`)}
            />
          </View>
        )}
        <View style={{ flexGrow: 1, flexBasis: "30%" }}>
          <Button
            label={t("email")}
            variant="secondary"
            palette={palette}
            onPress={() => void Linking.openURL(`mailto:${request.email}`)}
          />
        </View>
      </View>

      <View accessibilityLiveRegion="polite">
        {notice ? <Text style={{ color: palette.success, fontWeight: "600" }}>{notice}</Text> : null}
        <ErrorText message={error} palette={palette} />
      </View>

      <Card palette={palette}>
        <SectionTitle title={t("status")} palette={palette} />
        <PillRow<Status>
          label={t("status")}
          palette={palette}
          value={request.status}
          onChange={(status) => status !== request.status && void update({ status }, t("updated"))}
          options={(["new", "in_progress", "done"] as Status[]).map((value) => ({ value, label: tInbox(`statuses.${value}`) }))}
        />
        <Text style={[styles.muted, { color: palette.muted }]}>
          {request.assignee ? tInbox("assigned", { who: mine ? t("you") : request.assignee }) : "—"}
        </Text>
        {request.status !== "done" &&
          (mine ? (
            <Button
              label={tInbox("unassign")}
              variant="secondary"
              palette={palette}
              busy={busy}
              onPress={() => void update({ assignee: "" }, t("updated"))}
            />
          ) : (
            <Button
              label={tInbox("take")}
              palette={palette}
              busy={busy}
              onPress={() => void update({ assignee: "me", status: "in_progress" }, t("updated"))}
            />
          ))}
      </Card>

      <Card palette={palette}>
        <Field
          label={tInbox("notes")}
          palette={palette}
          value={notes ?? request.notes ?? ""}
          onChangeText={setNotes}
          multiline
          maxLength={4000}
          style={{ minHeight: 96, paddingTop: 12, textAlignVertical: "top" }}
        />
        <Button
          label={tInbox("saveNotes")}
          variant="secondary"
          palette={palette}
          busy={busy}
          disabled={notes === null}
          onPress={() => void update({ notes: notes ?? "" }, t("notesSaved"))}
        />
      </Card>

      {request.tenant_id && can("businesses.read") && (
        <Button label={tInbox("openBusiness")} variant="secondary" palette={palette} onPress={() => router.push(`/business/${request.tenant_id}`)} />
      )}
    </Screen>
  );
}
