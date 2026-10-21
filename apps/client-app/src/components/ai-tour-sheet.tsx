import { useState } from "react";
import { StyleSheet, View } from "react-native";
import { useTranslations } from "use-intl";

import { Sheet } from "@business-os/app-kit/components/sheet";
import { Text } from "@business-os/app-kit/components/text";
import { Button, Heading, styles as ui } from "@business-os/app-kit/components/ui";
import { type Palette, radius } from "@business-os/app-kit/lib/theme";
import { type Agent, AgentFace } from "@/components/agent-face";

const PAGES = 3;

/** The first guide of the AI team, as three pages. The chat in it is written in advance: it never
 * calls the model, so it costs no credits, and "Confirm" in it only shows what would happen. */
export function AiTourSheet({ visible, agents, canManage, palette, onClose }: { visible: boolean; agents: Agent[]; canManage: boolean; palette: Palette; onClose: () => void }) {
  const t = useTranslations("aiTeam.tour");
  const tTour = useTranslations("tour");
  const [page, setPage] = useState(0);
  const faces = agents.filter((a) => a.state === "active").slice(0, 6);
  const asker = agents.find((a) => a.key === "secretary" && a.state === "active") ?? faces[0];
  const last = page === PAGES - 1;

  const close = () => {
    setPage(0);
    onClose();
  };

  return (
    <Sheet
      visible={visible}
      onClose={close}
      palette={palette}
      title={page === 0 ? t("team.title") : page === 1 ? t("talk.title") : t("usage.title")}
      subtitle={tTour("progress", { current: page + 1, total: PAGES })}
      closeLabel={tTour("skip")}
      footer={
        <>
          <Button palette={palette} label={last ? tTour("done") : tTour("next")} onPress={() => (last ? close() : setPage(page + 1))} />
          {page > 0 ? <Button palette={palette} variant="secondary" label={tTour("back")} onPress={() => setPage(page - 1)} /> : null}
        </>
      }
    >
      {page === 0 && (
        <>
          <Text style={{ color: palette.foreground }}>{t("team.body")}</Text>
          {faces.map((agent) => (
            <View key={agent.key} style={s.person}>
              <AgentFace agent={agent} size={44} />
              <View style={{ flex: 1 }}>
                <Text style={{ color: palette.foreground, fontWeight: "600" }}>{agent.name}</Text>
                <Text style={{ color: palette.muted }}>{agent.role_title}</Text>
              </View>
            </View>
          ))}
        </>
      )}
      {page === 1 && (
        <>
          <Text style={{ color: palette.foreground }}>{t("talk.appBody")}</Text>
          <Text style={{ color: palette.foreground }}>{t("approvals.body")}</Text>
          {asker && <Simulation agent={asker} palette={palette} />}
        </>
      )}
      {page === 2 && (
        <>
          <Text style={{ color: palette.foreground }}>{t("usage.body")}</Text>
          <Heading palette={palette} level={2}>
            {t("hire.title")}
          </Heading>
          <Text style={{ color: palette.foreground }}>{canManage ? t("hire.body") : t("hire.bodyMember")}</Text>
        </>
      )}
    </Sheet>
  );
}

function Simulation({ agent, palette }: { agent: Agent; palette: Palette }) {
  const t = useTranslations("aiTeam.tour.simulation");
  const tAssistant = useTranslations("assistant");
  const [decision, setDecision] = useState<"confirm" | "reject" | null>(null);
  return (
    <View accessibilityLabel={t("label")} style={[s.sim, { borderColor: palette.border, backgroundColor: palette.background }]}>
      <View style={[s.bubble, { alignSelf: "flex-end", backgroundColor: palette.primary }]}>
        <Text style={{ color: palette.onPrimary }}>{t("question")}</Text>
      </View>
      <View style={{ flexDirection: "row", gap: 8, alignItems: "flex-start" }}>
        <AgentFace agent={agent} size={32} />
        <View style={{ flex: 1, gap: 8 }}>
          <View style={[s.bubble, { borderWidth: 1, borderColor: palette.border, backgroundColor: palette.surface }]}>
            <Text style={{ color: palette.foreground }}>{t("answer", { name: agent.name })}</Text>
          </View>
          <View style={[s.bubble, { borderWidth: 1, borderColor: palette.primary, backgroundColor: palette.surface, gap: 8 }]}>
            <Text style={[ui.muted, { color: palette.muted }]}>{tAssistant("needsConfirmation")}</Text>
            <Text style={{ color: palette.foreground, fontWeight: "500" }}>{t("card")}</Text>
            {decision ? (
              <Text accessibilityLiveRegion="polite" style={{ color: palette.muted }}>
                {t(decision === "confirm" ? "confirmed" : "rejected")}
              </Text>
            ) : (
              <View style={{ gap: 8 }}>
                <Button palette={palette} label={tAssistant("confirm")} onPress={() => setDecision("confirm")} />
                <Button palette={palette} variant="secondary" label={tAssistant("reject")} onPress={() => setDecision("reject")} />
              </View>
            )}
          </View>
        </View>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  person: { flexDirection: "row", alignItems: "center", gap: 12 },
  sim: { borderWidth: 1, borderStyle: "dashed", borderRadius: radius.card, padding: 12, gap: 12 },
  bubble: { borderRadius: radius.card, paddingHorizontal: 12, paddingVertical: 8 },
});
