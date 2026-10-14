import { Redirect } from "expo-router";
import { ActivityIndicator, View } from "react-native";

import { useTheme } from "@business-os/app-kit/providers/theme-provider";
import { useAreas } from "@/providers/area-provider";
import { useStaff } from "@/providers/staff-provider";

/** Start of the business area: waits for the business to load, then opens Today (or the
 * "closed" notice when the business is locked). */
export default function BusinessArea() {
  const { active } = useAreas();
  const { tenant, closedBusiness } = useStaff();
  const { palette } = useTheme();

  if (active && active.kind !== "business") return <Redirect href="/" />;
  if (closedBusiness) return <Redirect href="/closed" />;
  if (tenant) return <Redirect href="/today" />;
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: palette.background }}>
      <ActivityIndicator color={palette.primary} />
    </View>
  );
}
