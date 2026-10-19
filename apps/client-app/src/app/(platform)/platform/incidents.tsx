import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { useToast } from "@business-os/app-kit/components/toast";
import { BackBar, Badge, ListRow, PillRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { usePlatform } from "@/providers/platform-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

type Kind = "incident" | "maintenance" | "security";
const KINDS: Kind[] = ["incident", "maintenance", "security"];

/** Incident banners on the phone: the open and recent ones, resolving an open one, and showing a
 * new one (an outage, maintenance, a security event) in the language of the app. */
export default function Incidents() {
  const t = useTranslations("platform.incidents");
  const tApp = useTranslations("staffApp.incidents");
  const locale = useLocale() as "he" | "en";
  const { api, can } = usePlatform();
  const { palette } = useTheme();
  const toast = useToast();
  const allowed = can("incidents.manage");
  const [kind, setKind] = useState<Kind>("incident");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => (allowed ? unwrap(await api.GET("/platform/incidents")) : []), [api, allowed]);
  const { data, loading, reload } = useLoad(load);
  useFocusEffect(
    useCallback(() => {
      void reload();
    }, [reload]),
  );

  const when = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });
  const back = <BackBar label={tApp("back")} palette={palette} onPress={() => router.back()} />;
  const textOf = (incident: NonNullable<typeof data>[number]) => (incident.content[locale]?.title || incident.content[locale === "he" ? "en" : "he"]?.title) ?? "";

  const run = async (action: () => Promise<unknown>, done: string) => {
    setBusy(true);
    setError(null);
    try {
      await action();
      toast("success", done);
      await reload();
    } catch {
      setError(t("errors.generic"));
    } finally {
      setBusy(false);
    }
  };

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

  const open = (data ?? []).filter((i) => !i.resolved_at);
  const closed = (data ?? []).filter((i) => i.resolved_at).slice(0, 10);

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      {back}
      <Heading palette={palette}>{t("title")}</Heading>

      {open.length === 0 && !loading ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("empty")}</Text>
        </Card>
      ) : (
        <View style={{ gap: 8 }}>
          {open.map((incident) => (
            <Card key={incident.id} palette={palette}>
              <Badge label={t(`kinds.${incident.kind}`)} tone="danger" palette={palette} />
              <Text style={{ color: palette.foreground, fontSize: 16, fontWeight: "600", textAlign: "left" }}>{textOf(incident)}</Text>
              <Text style={[styles.muted, { color: palette.muted }]}>{when.format(new Date(incident.created_at))}</Text>
              <Button
                label={t("resolve")}
                palette={palette}
                variant="secondary"
                busy={busy}
                onPress={() =>
                  void run(async () => unwrap(await api.POST("/platform/incidents/{incident_id}/resolve", { params: { path: { incident_id: incident.id } } })), t("resolved"))
                }
              />
            </Card>
          ))}
        </View>
      )}

      <View style={{ gap: 8 }}>
        <SectionTitle title={tApp("newOne")} palette={palette} />
        <PillRow label={t("kind")} palette={palette} value={kind} onChange={setKind} options={KINDS.map((value) => ({ value, label: t(`kinds.${value}`) }))} />
        <Field label={t("titleField")} palette={palette} value={title} onChangeText={setTitle} maxLength={150} hint={tApp("titleHint")} />
        <Field label={t("bodyField")} palette={palette} value={body} onChangeText={setBody} maxLength={600} multiline />
        <ErrorText message={error} palette={palette} />
        <Button
          label={t("open")}
          palette={palette}
          busy={busy}
          disabled={!title.trim()}
          onPress={() =>
            void run(async () => {
              unwrap(await api.POST("/platform/incidents", { body: { kind, content: { [locale]: { title: title.trim(), body: body.trim() } }, status_url: "" } }));
              setTitle("");
              setBody("");
            }, t("opened"))
          }
        />
      </View>

      {closed.length > 0 && (
        <View style={{ gap: 8 }}>
          <SectionTitle title={t("resolved")} palette={palette} />
          {closed.map((incident) => (
            <ListRow
              key={incident.id}
              palette={palette}
              title={textOf(incident)}
              subtitle={`${t(`kinds.${incident.kind}`)} · ${when.format(new Date(incident.created_at))}`}
            />
          ))}
        </View>
      )}
    </Screen>
  );
}
