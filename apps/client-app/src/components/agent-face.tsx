import type { components } from "@business-os/api-client";
import { View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { AuthImage } from "@business-os/app-kit/components/auth-image";
import { initialOf } from "@business-os/app-kit/lib/ai-agents";

export type Agent = components["schemas"]["AgentCard"];

/** An agent's face: the uploaded picture over its color and initial (which stay if there is none). */
export function AgentFace({ agent, size = 40 }: { agent: Pick<Agent, "name" | "color" | "avatar_url">; size?: number }) {
  return (
    <View
      accessible={false}
      importantForAccessibility="no-hide-descendants"
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        overflow: "hidden",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: agent.color,
      }}
    >
      <Text style={{ color: "#ffffff", fontWeight: "700", fontSize: size * 0.42 }}>{initialOf(agent.name)}</Text>
      <AuthImage
        path={agent.avatar_url}
        style={{ position: "absolute", width: size, height: size, borderRadius: size / 2 }}
      />
    </View>
  );
}
