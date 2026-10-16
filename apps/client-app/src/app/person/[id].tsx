import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useState } from "react";
import { View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useTranslations } from "use-intl";

import { BackBar, ListRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { useToast } from "@business-os/app-kit/components/toast";
import { Button, Card, ErrorText, Heading, LoadError, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { confirm } from "@business-os/app-kit/lib/confirm";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { InstructorAvatar } from "@/components/instructor-avatar";
import { friendsError, personName } from "@/lib/friends";
import { useBusiness } from "@/providers/business-provider";

/** What the app shows of another client: picture, name, status and classes done together. */
export default function PersonScreen() {
  const t = useTranslations("friends");
  const { id } = useLocalSearchParams<{ id: string }>();
  const toast = useToast();
  const { api, scope, business, palette } = useBusiness();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!business || !id) return null;
    return unwrap(await api.GET("/client/people/{client_id}", { params: { ...scope, path: { client_id: id } } }));
  }, [api, scope, business, id]);
  const { data: person, error: loadError, reload } = useLoad(load);
  if (!business) return null;

  const act = async (call: () => Promise<{ error?: unknown; response: Response }>, done?: string) => {
    setBusy(true);
    setError(null);
    const result = await call().catch(() => null);
    setBusy(false);
    if (!result || !result.response.ok) return setError(t(`errors.${friendsError(result?.error)}`));
    if (done) toast("success", done);
    await reload();
  };

  const remove = async () => {
    if (!person) return;
    const ok = await confirm(t("removeTitle"), t("removeMessage", { name: person.first_name }), t("remove"), t("keep"));
    if (!ok) return;
    await act(() => api.DELETE("/client/friends/{client_id}", { params: { ...scope, path: { client_id: person.client_id } } }));
    router.back();
  };

  const name = person ? personName(person) : "";
  return (
    <Screen palette={palette}>
      <BackBar label={t("title")} palette={palette} onPress={() => router.back()} />
      {loadError !== undefined && !person && <LoadError palette={palette} onRetry={() => void reload()} />}
      {person && (
        <>
          <View style={{ alignItems: "center", gap: 8 }}>
            <InstructorAvatar name={name} path={person.avatar_url} palette={palette} size={96} />
            <Heading palette={palette}>{name}</Heading>
            {person.status_text ? <Text style={[styles.muted, { color: palette.muted }]}>{person.status_text}</Text> : null}
          </View>
          <Card palette={palette}>
            <Text style={[styles.h2, { color: palette.foreground }]}>{t("togetherTitle")}</Text>
            <Text style={[styles.muted, { color: palette.muted }]}>
              {person.shared_classes > 0 ? t("together", { count: person.shared_classes }) : t("noneTogether")}
            </Text>
          </Card>
          {"by_service" in person && person.by_service.length > 0 && (
            <>
              <SectionTitle title={t("byService")} palette={palette} />
              {person.by_service.map((row) => (
                <ListRow
                  key={row.service_id}
                  palette={palette}
                  title={row.service_name}
                  trailing={<Text style={[styles.muted, { color: palette.muted }]}>{row.shared_classes}</Text>}
                />
              ))}
            </>
          )}
          {person.friendship === "none" && (
            <Button
              label={t("addFriend")}
              palette={palette}
              busy={busy}
              onPress={() =>
                void act(
                  () => api.POST("/client/people/{client_id}/friend-request", { params: { ...scope, path: { client_id: person.client_id } } }),
                  t("requestSent"),
                )
              }
            />
          )}
          {person.friendship === "request_sent" && <Text style={[styles.muted, { color: palette.muted }]}>{t("pending")}</Text>}
          {person.friendship === "request_received" && person.friendship_id && (
            <Button
              label={t("accept")}
              palette={palette}
              busy={busy}
              onPress={() =>
                void act(
                  () => api.POST("/client/friends/requests/{friendship_id}/accept", { params: { ...scope, path: { friendship_id: person.friendship_id as string } } }),
                  t("nowFriends", { name: person.first_name }),
                )
              }
            />
          )}
          {person.friendship === "friends" && (
            <Button label={t("remove")} variant="danger" palette={palette} busy={busy} onPress={() => void remove()} />
          )}
          <ErrorText message={error} palette={palette} />
        </>
      )}
    </Screen>
  );
}
