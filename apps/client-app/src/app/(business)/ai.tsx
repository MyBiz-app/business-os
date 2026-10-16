import { router } from "expo-router";
import { useCallback } from "react";
import { Pressable, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useTranslations } from "use-intl";

import { BackBar } from "@business-os/app-kit/components/rows";
import { Card, EmptyState, Heading, LoadError, Screen, Skeleton, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { type Agent, AgentFace } from "@/components/agent-face";
import { useStaff } from "@/providers/staff-provider";

/** The business's AI team: every agent with its job, tap one to talk. */
export default function AiTeam() {
  const t = useTranslations("business.ai");
  const tTeam = useTranslations("aiTeam");
  const { api, scope, palette } = useStaff();
  const load = useCallback(async () => unwrap(await api.GET("/ai/team", { params: scope })), [api, scope]);
  const { data, error, loading, reload } = useLoad(load);

  const open = (agent: Agent) => router.push({ pathname: "/ai-chat", params: { agent: agent.key } });

  return (
    <Screen palette={palette} refreshing={loading && !!data} onRefresh={() => void reload()}>
      <BackBar label={t("back")} palette={palette} onPress={() => (router.canGoBack() ? router.back() : router.replace("/today"))} />
      <View style={{ gap: 4 }}>
        <Heading palette={palette}>{tTeam("title")}</Heading>
        <Text style={[styles.muted, { color: palette.muted }]}>{tTeam("subtitle")}</Text>
        {data && (
          <Text style={[styles.muted, { color: palette.muted }]}>
            {tTeam("usage", { used: Math.round(data.credits_used), included: data.credits_included })}
          </Text>
        )}
      </View>

      {error ? (
        <LoadError palette={palette} onRetry={() => void reload()} />
      ) : !data ? (
        <Skeleton palette={palette} height={72} />
      ) : data.agents.length === 0 ? (
        <EmptyState palette={palette} message={t("noAgents")} />
      ) : (
        data.agents.map((agent) => {
          const usable = agent.state === "active";
          return (
            <Pressable
              key={agent.key}
              accessibilityRole="button"
              accessibilityLabel={`${agent.name}, ${agent.role_title}. ${tTeam(`state.${agent.state}`)}`}
              accessibilityState={{ disabled: !usable }}
              disabled={!usable}
              onPress={() => open(agent)}
            >
              <Card palette={palette}>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 12, opacity: usable ? 1 : 0.6 }}>
                  <AgentFace agent={agent} size={52} />
                  <View style={{ flex: 1, gap: 2 }}>
                    <Text style={{ color: palette.foreground, fontWeight: "700", fontSize: 17 }}>{agent.name}</Text>
                    <Text style={{ color: palette.primary, fontWeight: "600" }}>{agent.role_title}</Text>
                    <Text numberOfLines={2} style={{ color: palette.muted }}>
                      {usable ? agent.topic : tTeam(`state.${agent.state}`)}
                    </Text>
                  </View>
                </View>
              </Card>
            </Pressable>
          );
        })
      )}
    </Screen>
  );
}
