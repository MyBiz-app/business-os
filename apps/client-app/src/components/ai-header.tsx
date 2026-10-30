import Ionicons from "@expo/vector-icons/Ionicons";
import { router, useSegments } from "expo-router";
import { StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslations } from "use-intl";

import { PressableScale } from "@business-os/app-kit/components/motion";
import { Text } from "@business-os/app-kit/components/text";
import { agentForTab } from "@business-os/app-kit/lib/ai-agents";
import { fixedColors, radius } from "@business-os/app-kit/lib/theme";
import { font } from "@business-os/app-kit/lib/typography";
import { useStaff } from "@/providers/staff-provider";

const BAR = 48;
const SIZE = 40;

/** The slim bar above the business tabs: the business name, and the AI button that opens the agent
 * that suits the screen. It sits in the layout, not over the content, so it never covers a list. */
export function AiHeader() {
  const t = useTranslations("business.ai");
  const { palette, tenant, can } = useStaff();
  const segments: string[] = useSegments();
  const insets = useSafeAreaInsets();
  const tab = segments[segments.length - 1];

  if (!tenant || !can("ai.use") || !tenant.modules.some((m) => m === "ai_basic" || m === "ai_pro")) return null;

  return (
    <View style={[local.bar, { paddingTop: insets.top, height: BAR + insets.top, backgroundColor: palette.background }]}>
      {/* Today's large title already names the business: show it here only on the other tabs. */}
      {tab === "today" ? (
        <View style={local.name} />
      ) : (
        <Text numberOfLines={1} style={[local.name, { color: palette.muted }]}>
          {tenant.name}
        </Text>
      )}
      <PressableScale
        accessibilityRole="button"
        accessibilityLabel={t("bubble")}
        onPress={() => router.push({ pathname: "/ai-chat", params: { agent: agentForTab(tab), context: tab ?? "" } })}
        style={[local.button, { backgroundColor: palette.ai }]}
      >
        <Ionicons name="sparkles" size={20} color={fixedColors.white} />
      </PressableScale>
    </View>
  );
}

const local = StyleSheet.create({
  bar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12, paddingHorizontal: 16 },
  name: { flex: 1, ...font.medium },
  button: { width: SIZE, height: SIZE, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
});
