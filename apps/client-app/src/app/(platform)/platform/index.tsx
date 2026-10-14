import { Redirect } from "expo-router";
import { ActivityIndicator, View } from "react-native";

import { useTheme } from "@business-os/app-kit/providers/theme-provider";
import { useAreas } from "@/providers/area-provider";
import { usePlatform } from "@/providers/platform-provider";

/** Start of the MyBiz area: waits for the team check, then opens Home. */
export default function PlatformArea() {
  const { active } = useAreas();
  const { onTeam } = usePlatform();
  const { palette } = useTheme();

  if (active && active.kind !== "platform") return <Redirect href="/" />;
  if (onTeam === false) return <Redirect href="/platform/not-team" />;
  if (onTeam) return <Redirect href="/platform/home" />;
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: palette.background }}>
      <ActivityIndicator color={palette.primary} />
    </View>
  );
}
