import { router } from "expo-router";
import Ionicons from "@expo/vector-icons/Ionicons";
import { useCallback, useEffect, useState } from "react";
import { Pressable, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useTranslations } from "use-intl";

import { BackBar } from "@business-os/app-kit/components/rows";
import { Card, EmptyState, Heading, LoadError, Screen, Skeleton, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { type Agent, AgentFace } from "@/components/agent-face";
import { AiTourSheet } from "@/components/ai-tour-sheet";
import { AiMeter } from "@/components/ai-meter";
import { useStaff } from "@/providers/staff-provider";

/** The business's AI team: every agent with its job, tap one to talk. */
export default function AiTeam() {
  const t = useTranslations("business.ai");
  const tTeam = useTranslations("aiTeam");
  const { api, scope, palette } = useStaff();
  const load = useCallback(async () => unwrap(await api.GET("/ai/team", { params: scope })), [api, scope]);
  const { data, error, loading, reload } = useLoad(load);
  const loadMeter = useCallback(async () => unwrap(await api.GET("/ai/meter", { params: scope })), [api, scope]);
  const { data: meter } = useLoad(loadMeter);

  // The first-time guide opens by itself until it has been finished or skipped once (per person); the "?" opens it again.
  const [touring, setTouring] = useState(false);
  useEffect(() => {
    let live = true;
    void api.GET("/me/tours").then((r) => {
      if (live && r.data && !r.data.seen.includes("ai_team")) setTouring(true);
    });
    return () => {
      live = false;
    };
  }, [api]);
  const endTour = () => {
    setTouring(false);
    void api.PUT("/me/tours/{key}", { params: { path: { key: "ai_team" } } });
  };

  const open = (agent: Agent) => router.push({ pathname: "/ai-chat", params: { agent: agent.key } });

  return (
    <Screen palette={palette} refreshing={loading && !!data} onRefresh={() => void reload()}>
      <BackBar label={t("back")} palette={palette} onPress={() => (router.canGoBack() ? router.back() : router.replace("/today"))} />
      <View style={{ gap: 4 }}>
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <Heading palette={palette}>{tTeam("title")}</Heading>
          <Pressable accessibilityRole="button" accessibilityLabel={tTeam("tour.help")} onPress={() => setTouring(true)} hitSlop={12}>
            <Ionicons name="help-circle-outline" size={26} color={palette.foreground} />
          </Pressable>
        </View>
        <Text style={[styles.muted, { color: palette.muted }]}>{tTeam("subtitle")}</Text>
      </View>
      {meter && <AiMeter meter={meter} palette={palette} />}

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
                    <Text style={{ color: palette.foreground, fontWeight: "600", fontSize: 17 }}>{agent.name}</Text>
                    <Text style={{ color: palette.primary, fontWeight: "500" }}>{agent.role_title}</Text>
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
      {data && <AiTourSheet visible={touring} agents={data.agents} canManage={data.can_manage} palette={palette} onClose={endTour} />}
    </Screen>
  );
}
