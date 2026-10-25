import { router } from "expo-router";
import { useCallback, useState } from "react";
import { Share, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { BackBar, Badge, SectionTitle } from "@business-os/app-kit/components/rows";
import { useToast } from "@business-os/app-kit/components/toast";
import { Button, Card, ErrorText, Field, Heading, LoadError, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { WEB_URL } from "@business-os/app-kit/lib/env";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { PersonRow } from "@/components/person-row";
import { forgetShared } from "@/lib/client-data";
import { friendsError } from "@/lib/friends";
import { useDataContext } from "@/lib/use-data-context";
import { useBusiness } from "@/providers/business-provider";

/** Tells a friend code from an email or a phone number, so one box does all three. */
function lookupBody(value: string): { code?: string; phone?: string; email?: string } {
  const text = value.trim();
  if (text.includes("@")) return { email: text };
  if (/^[+\d][\d\s()-]{5,}$/.test(text)) return { phone: text };
  return { code: text.toUpperCase() };
}

/** Friends inside this business: my code, requests, my friends, and invitations to classes. */
export default function Friends() {
  const t = useTranslations("friends");
  const tProfile = useTranslations("client.profile");
  const locale = useLocale();
  const toast = useToast();
  const { api, scope, business, palette } = useBusiness();
  const ctx = useDataContext();
  const [lookup, setLookup] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!business) return null;
    const settings = unwrap(await api.GET("/client/friends/settings", { params: scope }));
    if (!settings.enabled) return { settings, friends: [], requests: { incoming: [], outgoing: [] }, invites: [] };
    const [friends, requests, invites] = await Promise.all([
      api.GET("/client/friends", { params: scope }).then(unwrap),
      api.GET("/client/friends/requests", { params: scope }).then(unwrap),
      api.GET("/client/invites", { params: scope }).then(unwrap),
    ]);
    return { settings, friends, requests, invites };
  }, [api, scope, business]);
  const { data, error: loadError, reload } = useLoad(load);
  if (!business) return null;

  /** Runs one friends call, shows its error in words, and reloads the lists. */
  const act = async (call: () => Promise<{ error?: unknown; response: Response }>, done?: string) => {
    setBusy(true);
    setError(null);
    const result = await call().catch(() => null);
    setBusy(false);
    if (!result || !result.response.ok) {
      setError(t(`errors.${friendsError((result?.error as unknown) ?? undefined)}`));
      return false;
    }
    if (done) toast("success", done);
    if (ctx) void forgetShared(ctx, "friend-settings");
    await reload();
    return true;
  };

  const sendRequest = async () => {
    if (!lookup.trim()) return;
    const ok = await act(
      () => api.POST("/client/friends/requests", { params: scope, body: lookupBody(lookup) }),
      t("requestSent"),
    );
    if (ok) setLookup("");
  };

  // With the business's join code, the message carries a link a friend can open to join first.
  const share = () => {
    if (!data) return;
    const code = data.settings.friend_code;
    const message = business.join_code
      ? t("shareMessageLink", { business: business.name, code, link: `${WEB_URL}/join/${business.join_code}` })
      : t("shareMessage", { business: business.name, code });
    void Share.share({ message });
  };

  const hours = (iso: string) =>
    new Intl.DateTimeFormat(locale, {
      weekday: "short",
      day: "numeric",
      month: "short",
      hour: "numeric",
      minute: "2-digit",
      timeZone: business.time_zone,
    }).format(new Date(iso));

  return (
    <Screen palette={palette} refreshing={false} onRefresh={() => void reload()}>
      <BackBar label={tProfile("title")} palette={palette} onPress={() => router.back()} />
      <Heading palette={palette}>{t("title")}</Heading>
      {loadError !== undefined && !data && <LoadError palette={palette} onRetry={() => void reload()} />}
      {data && !data.settings.enabled && (
        <Text style={[styles.muted, { color: palette.muted }]}>{t("disabled")}</Text>
      )}
      {data?.settings.enabled && (
        <>
          <Card palette={palette}>
            <Text style={[styles.muted, { color: palette.muted }]}>{t("myCode")}</Text>
            <Text
              accessibilityLabel={t("myCodeLabel", { code: data.settings.friend_code.split("").join(" ") })}
              style={[styles.h2, { color: palette.foreground, letterSpacing: 4, textAlign: "left", writingDirection: "ltr" }]}
            >
              {data.settings.friend_code}
            </Text>
            <Button label={t("share")} variant="secondary" palette={palette} onPress={() => void share()} />
          </Card>

          <SectionTitle title={t("add")} palette={palette} />
          <Field
            label={t("addLabel")}
            hint={t("addHint")}
            palette={palette}
            value={lookup}
            onChangeText={setLookup}
            autoCapitalize="none"
            autoCorrect={false}
            dir="ltr"
            returnKeyType="send"
            onSubmitEditing={() => void sendRequest()}
          />
          <Button label={t("sendRequest")} palette={palette} busy={busy} disabled={!lookup.trim()} onPress={() => void sendRequest()} />
          <ErrorText message={error} palette={palette} />

          {data.invites.length > 0 && <SectionTitle title={t("invites")} palette={palette} />}
          {data.invites.map((invite) => (
            <Card key={invite.id} palette={palette}>
              <Text style={[styles.h2, { color: palette.foreground }]}>{invite.service_name}</Text>
              <Text style={[styles.muted, { color: palette.muted }]}>{hours(invite.starts_at)}</Text>
              <Text style={[styles.muted, { color: palette.muted }]}>
                {invite.direction === "received"
                  ? t("invitedBy", { name: invite.other_first_name ?? "" })
                  : t("youInvited", { name: invite.other_first_name ?? "" })}
              </Text>
              {invite.direction === "received" ? (
                <View style={{ gap: 8 }}>
                  <Button
                    label={t("acceptInvite")}
                    palette={palette}
                    busy={busy}
                    onPress={() =>
                      void act(
                        () => api.POST("/client/invites/{invite_id}/accept", { params: { ...scope, path: { invite_id: invite.id } } }),
                        t("inviteAccepted"),
                      )
                    }
                  />
                  <Button
                    label={t("declineInvite")}
                    variant="secondary"
                    palette={palette}
                    busy={busy}
                    onPress={() =>
                      void act(() => api.POST("/client/invites/{invite_id}/decline", { params: { ...scope, path: { invite_id: invite.id } } }))
                    }
                  />
                </View>
              ) : (
                <Button
                  label={t("cancelInvite")}
                  variant="secondary"
                  palette={palette}
                  busy={busy}
                  onPress={() =>
                    void act(() => api.DELETE("/client/invites/{invite_id}", { params: { ...scope, path: { invite_id: invite.id } } }))
                  }
                />
              )}
            </Card>
          ))}

          {data.requests.incoming.length > 0 && <SectionTitle title={t("requests")} palette={palette} />}
          {data.requests.incoming.map((person) => (
            <Card key={person.client_id} palette={palette}>
              <PersonRow person={person} palette={palette} onPress={() => router.push(`/person/${person.client_id}`)} />
              <View style={{ gap: 8 }}>
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
                <Button
                  label={t("decline")}
                  variant="secondary"
                  palette={palette}
                  busy={busy}
                  onPress={() =>
                    void act(() => api.DELETE("/client/friends/requests/{friendship_id}", { params: { ...scope, path: { friendship_id: person.friendship_id as string } } }))
                  }
                />
              </View>
            </Card>
          ))}
          {data.requests.outgoing.map((person) => (
            <PersonRow
              key={person.client_id}
              person={person}
              palette={palette}
              onPress={() => router.push(`/person/${person.client_id}`)}
              trailing={<Badge label={t("pending")} palette={palette} />}
            />
          ))}

          <SectionTitle title={t("mine", { count: data.friends.length })} palette={palette} />
          {data.friends.length === 0 && <Text style={[styles.muted, { color: palette.muted }]}>{t("none")}</Text>}
          {data.friends.map((person) => (
            <PersonRow key={person.client_id} person={person} palette={palette} onPress={() => router.push(`/person/${person.client_id}`)} />
          ))}

          <SectionTitle title={t("privacy")} palette={palette} />
          <Text style={[styles.muted, { color: palette.muted }]}>
            {data.settings.visible ? t("visibleOn") : t("visibleOff")}
          </Text>
          <Button
            label={data.settings.visible ? t("hideMe") : t("showMe")}
            variant="secondary"
            palette={palette}
            busy={busy}
            onPress={() =>
              void act(() => api.PATCH("/client/friends/settings", { params: scope, body: { visible: !data.settings.visible } }))
            }
          />
        </>
      )}
    </Screen>
  );
}
