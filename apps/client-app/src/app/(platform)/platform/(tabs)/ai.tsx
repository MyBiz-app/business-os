import { useCallback, useState } from "react";
import { View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { Badge, ListRow, PillRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { ApiError, unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { usePlatform } from "@/providers/platform-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

const ROLES = ["manager", "support", "health", "billing", "growth"] as const;
type Role = (typeof ROLES)[number];
type Turn = { role: "user" | "assistant"; text: string };
const KNOWN = ["ai_paused", "conversation_limit", "ai_busy", "ai_unavailable", "ai_not_configured"];

/** MyBiz's own AI helpers on the phone: pick a helper, ask, and come back to an earlier chat. The
 * helpers only read and draft; the conversations are saved on the server. */
export default function Ai() {
  const t = useTranslations("platform.ai");
  const tApp = useTranslations("staffApp.ai");
  const locale = useLocale();
  const { api, can } = usePlatform();
  const { palette } = useTheme();
  const [role, setRole] = useState<Role>("manager");
  const [chatId, setChatId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const allowed = can("usage.read");
  const loadChats = useCallback(async () => (allowed ? unwrap(await api.GET("/platform/ai/assistant/conversations")) : []), [api, allowed]);
  const { data: chats, loading, reload } = useLoad(loadChats);

  const fail = (caught: unknown) => {
    const detail = caught instanceof ApiError ? caught.detail : "";
    setError(t(`errors.${KNOWN.includes(detail ?? "") ? (detail as "ai_paused") : "generic"}`));
  };

  const send = async () => {
    const question = text.trim();
    if (!question || busy) return;
    setBusy(true);
    setError(null);
    setText("");
    setTurns((all) => [...all, { role: "user", text: question }]);
    let id = chatId;
    try {
      if (!id) {
        id = unwrap(await api.POST("/platform/ai/assistant/conversations", { body: { role } })).id;
        setChatId(id);
      }
      const chat = unwrap(await api.POST("/platform/ai/assistant/conversations/{chat_id}/messages", { params: { path: { chat_id: id } }, body: { text: question } }));
      setTurns(chat.turns);
      void reload();
    } catch (caught) {
      fail(caught);
    } finally {
      setBusy(false);
    }
  };

  const open = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      const chat = unwrap(await api.GET("/platform/ai/assistant/conversations/{chat_id}", { params: { path: { chat_id: id } } }));
      setChatId(chat.id);
      setRole(chat.role);
      setTurns(chat.turns);
    } catch (caught) {
      fail(caught);
    } finally {
      setBusy(false);
    }
  };

  const startNew = () => {
    setChatId(null);
    setTurns([]);
    setError(null);
  };

  if (!allowed) {
    return (
      <Screen palette={palette}>
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{tApp("noPermission")}</Text>
        </Card>
      </Screen>
    );
  }

  const stamp = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });
  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <Heading palette={palette}>{tApp("title")}</Heading>
      <PillRow
        label={t("assistantRole")}
        palette={palette}
        value={role}
        onChange={(next) => chatId === null && setRole(next)}
        options={ROLES.map((value) => ({ value, label: t(`roles.${value}`) }))}
      />
      <Text style={[styles.muted, { color: palette.muted }]}>{t(`roleHints.${role}`)}</Text>

      <View style={{ gap: 8 }}>
        {turns.map((turn, index) => (
          <View
            key={index}
            style={{
              alignSelf: turn.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "90%",
              borderRadius: 16,
              padding: 12,
              borderWidth: turn.role === "user" ? 0 : 1,
              borderColor: palette.border,
              backgroundColor: turn.role === "user" ? palette.surface : "transparent",
            }}
          >
            <Text style={{ color: palette.foreground, fontSize: 15, textAlign: "left" }}>{turn.text}</Text>
          </View>
        ))}
        {busy && <Text style={[styles.muted, { color: palette.muted }]}>{t("thinking")}</Text>}
      </View>
      <ErrorText message={error} palette={palette} />

      <Field label={t("question")} palette={palette} value={text} onChangeText={setText} maxLength={4000} multiline />
      <Button label={t("send")} palette={palette} onPress={() => void send()} busy={busy} disabled={!text.trim()} />
      {chatId !== null && <Button label={t("newChat")} palette={palette} variant="secondary" onPress={startNew} />}

      {(chats ?? []).length > 0 && (
        <View style={{ gap: 8 }}>
          <SectionTitle title={t("history")} palette={palette} />
          {(chats ?? []).map((chat) => (
            <ListRow
              key={chat.id}
              palette={palette}
              title={chat.title ?? t("untitled")}
              subtitle={stamp.format(new Date(chat.updated_at))}
              trailing={<Badge label={t(`roles.${chat.role as Role}`)} tone={chat.id === chatId ? "primary" : "muted"} palette={palette} />}
              onPress={() => void open(chat.id)}
            />
          ))}
        </View>
      )}
    </Screen>
  );
}
