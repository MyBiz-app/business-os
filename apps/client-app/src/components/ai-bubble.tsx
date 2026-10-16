import Ionicons from "@expo/vector-icons/Ionicons";
import { router, useSegments } from "expo-router";
import { Pressable, useWindowDimensions } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslations } from "use-intl";

import { agentForTab } from "@business-os/app-kit/lib/ai-agents";
import { useStaff } from "@/providers/staff-provider";

const WIDE = 900; // the tabs move to a side rail from this width (see tab-options)
const SIZE = 56;

/** The floating AI button over the business tabs: opens the agent that suits the screen. */
export function AiBubble() {
  const t = useTranslations("business.ai");
  const { palette, tenant, can } = useStaff();
  const segments: string[] = useSegments();
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const tab = segments[segments.length - 1];

  if (!tenant || !can("ai.use") || !tenant.modules.some((m) => m === "ai_basic" || m === "ai_pro")) return null;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={t("bubble")}
      onPress={() => router.push({ pathname: "/ai-chat", params: { agent: agentForTab(tab), context: tab ?? "" } })}
      style={({ pressed }) => ({
        position: "absolute",
        end: 16,
        bottom: insets.bottom + (width >= WIDE ? 24 : 84),
        width: SIZE,
        height: SIZE,
        borderRadius: SIZE / 2,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: palette.ai,
        opacity: pressed ? 0.85 : 1,
        boxShadow: "0px 4px 12px rgba(17, 24, 39, 0.28)",
      })}
    >
      <Ionicons name="sparkles" size={26} color="#ffffff" />
    </Pressable>
  );
}
