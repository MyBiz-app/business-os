import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useTranslations } from "use-intl";

import { useToast } from "@business-os/app-kit/components/toast";
import { Button, ErrorText, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { PersonRow } from "@/components/person-row";
import { friendsError, type Person } from "@/lib/friends";
import { forgetSessionPeople } from "@/lib/session-people";
import { useBusiness } from "@/providers/business-provider";

type Loaded = { participants: Person[]; friends: Person[]; invited: Set<string> };

/** Under a booked class: who else is coming, and "invite a friend" (their spot is held for them). */
export function SessionFriends({
  sessionId,
  alwaysOpen = false,
  canInviteFriends = true,
  onLeave,
}: {
  sessionId: string;
  /** Show the lists straight away, without the toggle button (inside the class details sheet). */
  alwaysOpen?: boolean;
  /** Only someone who is booked can invite; others just see who is coming. */
  canInviteFriends?: boolean;
  /** Called before leaving for a person's profile (to close the sheet it sits in). */
  onLeave?: () => void;
}) {
  const t = useTranslations("friends");
  const toast = useToast();
  const { api, scope, palette } = useBusiness();
  const [data, setData] = useState<Loaded | null>(null);
  const [open, setOpen] = useState(alwaysOpen);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [participants, friends, invites] = await Promise.all([
      api.GET("/client/sessions/{session_id}/participants", { params: { ...scope, path: { session_id: sessionId } } }).then(unwrap),
      api.GET("/client/friends", { params: scope }).then(unwrap),
      api.GET("/client/invites", { params: scope }).then(unwrap),
    ]);
    const invited = new Set(invites.filter((i) => i.session_id === sessionId && i.direction === "sent").map((i) => i.other_client_id));
    setData({ participants, friends, invited });
  }, [api, scope, sessionId]);

  useEffect(() => {
    if (alwaysOpen) void load().catch(() => setError(t("errors.generic")));
  }, [alwaysOpen, load, t]);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    setError(null);
    if (next) await load().catch(() => setError(t("errors.generic")));
  };

  const invite = async (friend: Person) => {
    setBusy(true);
    setError(null);
    const result = await api
      .POST("/client/sessions/{session_id}/invites", {
        params: { ...scope, path: { session_id: sessionId } },
        body: { friend_id: friend.client_id },
      })
      .catch(() => null);
    setBusy(false);
    if (!result?.response.ok) return setError(t(`errors.${friendsError(result?.error)}`));
    toast("success", t("inviteSent", { name: friend.first_name }));
    forgetSessionPeople(sessionId);
    await load().catch(() => undefined);
  };

  const inClass = new Set(data?.participants.map((p) => p.client_id));
  const canInvite = !canInviteFriends ? [] : data?.friends.filter((f) => !inClass.has(f.client_id) && !data.invited.has(f.client_id)) ?? [];

  return (
    <View style={{ gap: 8 }}>
      {!alwaysOpen && <Button label={open ? t("hideFriends") : t("friendsInClass")} variant="secondary" palette={palette} onPress={() => void toggle()} />}
      {open && data && (
        <>
          <Text style={[styles.h2, { color: palette.foreground }]}>{t("whosComing")}</Text>
          {data.participants.length === 0 && <Text style={[styles.muted, { color: palette.muted }]}>{t("noParticipants")}</Text>}
          {data.participants.map((person) => (
            <PersonRow key={person.client_id} person={person} palette={palette} onPress={() => {
                onLeave?.();
                router.push(`/person/${person.client_id}`);
              }} />
          ))}
          {canInvite.length > 0 && <Text style={[styles.h2, { color: palette.foreground }]}>{t("inviteFriend")}</Text>}
          {canInvite.map((friend) => (
            <PersonRow
              key={friend.client_id}
              person={friend}
              palette={palette}
              trailing={<Button label={t("invite")} palette={palette} busy={busy} onPress={() => void invite(friend)} />}
            />
          ))}
        </>
      )}
      <ErrorText message={error} palette={palette} />
    </View>
  );
}
