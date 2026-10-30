import type { components } from "@business-os/api-client";
import Ionicons from "@expo/vector-icons/Ionicons";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { I18nManager, KeyboardAvoidingView, Platform, Pressable, ScrollView, type ScrollViewInstance, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Text } from "@business-os/app-kit/components/text";
import { useTranslations } from "use-intl";

import { BackBar } from "@business-os/app-kit/components/rows";
import { ErrorText, LoadError } from "@business-os/app-kit/components/ui";
import { pickAgent } from "@business-os/app-kit/lib/ai-agents";
import { ApiError, unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { AiActionCard } from "@/components/ai-action-card";
import { type Agent, AgentFace } from "@/components/agent-face";
import { useStaff } from "@/providers/staff-provider";
import { radius } from "@business-os/app-kit/lib/theme";
import { Spinner } from "@business-os/app-kit/components/spinner";

type Conversation = components["schemas"]["app__api__assistant__Conversation"];
type ChatError = "ai_not_configured" | "ai_busy" | "ai_unavailable" | "ai_limit_reached" | "ai_user_limit_reached" | "ai_daily_pace_reached" | "ai_rate_limited" | "generic";

const KNOWN: readonly string[] = ["ai_not_configured", "ai_busy", "ai_unavailable", "ai_limit_reached", "ai_user_limit_reached", "ai_daily_pace_reached", "ai_rate_limited"];
const chatError = (error: unknown): ChatError =>
  error instanceof ApiError && error.detail && KNOWN.includes(error.detail) ? (error.detail as ChatError) : "generic";

/** A full-screen chat with one AI agent: switch agents on top, confirm what it prepared in cards. */
export default function AiChat() {
  const t = useTranslations("business.ai");
  const tTeam = useTranslations("aiTeam");
  const tAssistant = useTranslations("assistant");
  const params = useLocalSearchParams<{ agent?: string; context?: string }>();
  const { api, scope, palette, branch } = useStaff();
  const [agentKey, setAgentKey] = useState<string | undefined>(params.agent);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [waitingFor, setWaitingFor] = useState<string | null>(null);
  const [error, setError] = useState<ChatError | null>(null);
  const [deciding, setDeciding] = useState<string | null>(null);
  const [text, setText] = useState("");
  const scroller = useRef<ScrollViewInstance>(null);

  const loadTeam = useCallback(async () => unwrap(await api.GET("/ai/team", { params: scope })), [api, scope]);
  const { data: team, error: teamError, reload } = useLoad(loadTeam);
  const agent = team ? pickAgent(team.agents, agentKey) : undefined;
  const turns = conversation?.turns ?? [];
  const busy = waitingFor !== null;

  useEffect(() => {
    scroller.current?.scrollToEnd({ animated: true });
  }, [turns.length, waitingFor]);

  /** Starts a fresh chat with an agent; the last exchange of the current chat comes along. */
  const startWith = async (target: Agent): Promise<Conversation> =>
    unwrap(
      await api.POST("/ai/conversations", {
        params: scope,
        body: {
          agent_key: target.key,
          location_ids: branch ? [branch.id] : null,
          handoff_from: conversation?.id ?? null,
          page_context: params.context ?? null,
        },
      }),
    );

  const send = async (value: string) => {
    const question = value.trim();
    if (!question || busy || !agent) return;
    setText("");
    setError(null);
    setWaitingFor(question);
    try {
      const current = conversation ?? (await startWith(agent));
      const next = unwrap(
        await api.POST("/ai/conversations/{conversation_id}/messages", {
          params: { ...scope, path: { conversation_id: current.id } },
          body: { text: question },
        }),
      );
      setConversation(next);
    } catch (caught) {
      setError(chatError(caught));
      setText(question);
    } finally {
      setWaitingFor(null);
    }
  };

  const switchTo = (target: Agent) => {
    if (target.key === agent?.key) return;
    setAgentKey(target.key);
    setConversation(null);
    setError(null);
  };

  const handoff = async (key: string) => {
    const target = team?.agents.find((a) => a.key === key && a.state === "active");
    if (!target) return;
    setError(null);
    setWaitingFor("");
    try {
      const started = await startWith(target);
      setAgentKey(target.key);
      setConversation(started);
    } catch (caught) {
      setError(chatError(caught));
    } finally {
      setWaitingFor(null);
    }
  };

  const decide = async (actionId: string, decision: "confirm" | "reject") => {
    if (!conversation) return;
    setDeciding(actionId);
    const params = { ...scope, path: { action_id: actionId } };
    try {
      if (decision === "confirm") unwrap(await api.POST("/ai/pending-actions/{action_id}/confirm", { params }));
      else unwrap(await api.POST("/ai/pending-actions/{action_id}/reject", { params }));
    } catch {
      // The card shows the action's final state (expired, failed) after the reload below.
    }
    try {
      setConversation(unwrap(await api.GET("/ai/conversations/{conversation_id}", { params: { ...scope, path: { conversation_id: conversation.id } } })));
    } finally {
      setDeciding(null);
    }
  };

  const suggestions =
    agent && turns.length === 0 && !busy
      ? (["s1", "s2", "s3"] as const).map((k) => tTeam(`suggestions.${agent.builtin ? agent.key : "custom"}.${k}` as "suggestions.chief.s1"))
      : [];

  return (
    <SafeAreaView edges={["top", "left", "right", "bottom"]} style={{ flex: 1, backgroundColor: palette.background }}>
      <KeyboardAvoidingView style={{ flex: 1, width: "100%", maxWidth: 720, alignSelf: "center" }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <View style={{ paddingHorizontal: 16, paddingTop: 8, gap: 8 }}>
          <BackBar label={t("back")} palette={palette} onPress={() => (router.canGoBack() ? router.back() : router.replace("/ai"))} />
          {agent && (
            <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }} accessible accessibilityRole="header">
              <AgentFace agent={agent} size={44} />
              <View style={{ flex: 1 }}>
                <Text style={{ color: palette.foreground, fontWeight: "600", fontSize: 17 }}>{agent.name}</Text>
                <Text numberOfLines={1} style={{ color: palette.muted }}>
                  {agent.role_title}
                </Text>
              </View>
              {turns.length > 0 && (
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={tTeam("newChat")}
                  hitSlop={8}
                  onPress={() => {
                    setConversation(null);
                    setError(null);
                  }}
                  style={{ padding: 8 }}
                >
                  <Ionicons name="add-circle-outline" size={26} color={palette.primary} />
                </Pressable>
              )}
            </View>
          )}
          {team && team.agents.filter((a) => a.state === "active").length > 1 && (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} accessibilityLabel={tTeam("switchAgent")} contentContainerStyle={{ gap: 10, paddingVertical: 4 }}>
              {team.agents
                .filter((a) => a.state === "active")
                .map((other) => (
                  <Pressable
                    key={other.key}
                    accessibilityRole="button"
                    accessibilityLabel={`${other.name}, ${other.role_title}`}
                    accessibilityState={{ selected: other.key === agent?.key }}
                    onPress={() => switchTo(other)}
                    style={{
                      borderRadius: radius.card,
                      padding: 2,
                      borderWidth: 2,
                      borderColor: other.key === agent?.key ? other.color : "transparent",
                      opacity: other.key === agent?.key ? 1 : 0.65,
                    }}
                  >
                    <AgentFace agent={other} size={36} />
                  </Pressable>
                ))}
            </ScrollView>
          )}
        </View>

        {teamError ? (
          <LoadError palette={palette} onRetry={() => void reload()} />
        ) : !team ? (
          <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
            <Spinner color={palette.primary} />
          </View>
        ) : !agent ? (
          <View style={{ flex: 1, padding: 24 }}>
            <Text style={{ color: palette.muted, textAlign: "center" }}>{t("noAgents")}</Text>
          </View>
        ) : (
          <ScrollView
            ref={scroller}
            style={{ flex: 1 }}
            contentContainerStyle={{ padding: 16, gap: 12 }}
            keyboardShouldPersistTaps="handled"
            keyboardDismissMode="interactive"
          >
            {turns.length === 0 && !busy && (
              <View style={{ alignItems: "center", gap: 8, paddingVertical: 24 }}>
                <AgentFace agent={agent} size={72} />
                <Text style={{ color: palette.foreground, fontWeight: "600", fontSize: 17, textAlign: "center" }}>
                  {tTeam("greeting", { name: agent.name })}
                </Text>
                {agent.topic ? <Text style={{ color: palette.muted, textAlign: "center" }}>{agent.topic}</Text> : null}
              </View>
            )}
            {turns.map((turn, index) =>
              turn.role === "user" ? (
                <View key={index} style={{ alignItems: "flex-end" }}>
                  <View style={{ maxWidth: "85%", backgroundColor: palette.primary, borderRadius: radius.card, paddingHorizontal: 14, paddingVertical: 10 }}>
                    <Text accessibilityLabel={`${tAssistant("you")} ${turn.text}`} style={{ color: palette.onPrimary }}>
                      {turn.text}
                    </Text>
                  </View>
                </View>
              ) : (
                <View key={index} style={{ gap: 8, maxWidth: "92%", alignItems: "flex-start" }}>
                  <View style={{ backgroundColor: palette.surface, borderColor: palette.border, borderWidth: 1, borderRadius: radius.card, paddingHorizontal: 14, paddingVertical: 10 }}>
                    <Text accessibilityLabel={`${agent.name}: ${turn.text || tAssistant("noAnswer")}`} style={{ color: palette.foreground }}>
                      {turn.text || tAssistant("noAnswer")}
                    </Text>
                  </View>
                  {turn.pending_actions.map((action) => (
                    <View key={action.id} style={{ alignSelf: "stretch" }}>
                      <AiActionCard action={action} palette={palette} busy={deciding === action.id} onDecide={(id, d) => void decide(id, d)} />
                    </View>
                  ))}
                  {turn.suggestions.map((suggestion) => {
                    const target = team.agents.find((a) => a.key === suggestion.agent_key);
                    return (
                      <Pressable
                        key={suggestion.agent_key}
                        accessibilityRole="button"
                        onPress={() => void handoff(suggestion.agent_key)}
                        style={{ borderWidth: 1, borderColor: palette.ai, borderRadius: radius.control, padding: 12, gap: 2, alignSelf: "stretch" }}
                      >
                        <Text style={{ color: palette.foreground, fontWeight: "500" }}>
                          {tTeam("handoff", { name: target?.name ?? suggestion.agent_key })}
                        </Text>
                        <Text style={{ color: palette.muted }}>{suggestion.reason}</Text>
                      </Pressable>
                    );
                  })}
                </View>
              ),
            )}
            {waitingFor ? (
              <View style={{ alignItems: "flex-end" }}>
                <View style={{ maxWidth: "85%", backgroundColor: palette.primary, borderRadius: radius.card, paddingHorizontal: 14, paddingVertical: 10 }}>
                  <Text style={{ color: palette.onPrimary }}>{waitingFor}</Text>
                </View>
              </View>
            ) : null}
            {busy && (
              <View accessibilityRole="progressbar" accessibilityLabel={tTeam("thinking", { name: agent.name })} style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                <Spinner color={palette.ai} />
                <Text style={{ color: palette.muted }}>{tTeam("thinking", { name: agent.name })}</Text>
              </View>
            )}
          </ScrollView>
        )}

        {agent && (
          <View style={{ paddingHorizontal: 16, paddingBottom: 8, gap: 8 }}>
            {error ? <ErrorText palette={palette} message={tAssistant(`errors.${error}`)} /> : null}
            {suggestions.length > 0 && (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} keyboardShouldPersistTaps="handled" contentContainerStyle={{ gap: 8 }}>
                {suggestions.map((suggestion) => (
                  <Pressable
                    key={suggestion}
                    accessibilityRole="button"
                    onPress={() => void send(suggestion)}
                    style={{ borderWidth: 1, borderColor: palette.border, backgroundColor: palette.surface, borderRadius: radius.card, paddingHorizontal: 14, minHeight: 44, justifyContent: "center" }}
                  >
                    <Text style={{ color: palette.foreground }}>{suggestion}</Text>
                  </Pressable>
                ))}
              </ScrollView>
            )}
            <View style={{ flexDirection: "row", alignItems: "flex-end", gap: 8 }}>
              <TextInput
                value={text}
                onChangeText={setText}
                accessibilityLabel={tAssistant("question")}
                placeholder={tTeam("placeholder", { name: agent.name })}
                placeholderTextColor={palette.muted}
                multiline
                maxLength={2000}
                editable={!busy}
                style={{
                  flex: 1,
                  minHeight: 48,
                  maxHeight: 120,
                  borderWidth: 1,
                  borderColor: palette.border,
                  backgroundColor: palette.surface,
                  color: palette.foreground,
                  borderRadius: radius.card,
                  paddingHorizontal: 16,
                  paddingVertical: 12,
                  fontSize: 15,
                }}
              />
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={tAssistant("send")}
                accessibilityState={{ disabled: busy || !text.trim() }}
                disabled={busy || !text.trim()}
                onPress={() => void send(text)}
                style={{ width: 48, height: 48, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", backgroundColor: palette.primary, opacity: busy || !text.trim() ? 0.5 : 1 }}
              >
                <Ionicons name="send" size={20} color={palette.onPrimary} style={{ transform: [{ scaleX: I18nManager.isRTL ? -1 : 1 }] }} />
              </Pressable>
            </View>
          </View>
        )}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
