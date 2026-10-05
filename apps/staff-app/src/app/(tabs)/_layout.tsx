import Ionicons from "@expo/vector-icons/Ionicons";
import { Redirect, Tabs } from "expo-router";
import { ActivityIndicator, type ColorValue, View } from "react-native";
import { useTranslations } from "use-intl";

import { useSession } from "@business-os/app-kit/providers/session-provider";
import { useStaff } from "@/providers/staff-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

type IconName = React.ComponentProps<typeof Ionicons>["name"];

const icon =
  (name: IconName) =>
  ({ color, size }: { color: ColorValue; size: number }) => <Ionicons name={name} color={color as string} size={size} />;

/** The MyBiz team's tabs; each one appears only for someone whose permissions cover it. */
export default function TabsLayout() {
  const { session, loading } = useSession();
  const { onTeam, can } = useStaff();
  const { palette } = useTheme();
  const t = useTranslations("staffApp.tabs");

  if (!loading && !session) return <Redirect href="/sign-in" />;
  if (onTeam === false) return <Redirect href="/not-staff" />;
  if (!onTeam) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: palette.background }}>
        <ActivityIndicator color={palette.primary} />
      </View>
    );
  }

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: palette.primary,
        tabBarInactiveTintColor: palette.muted,
        tabBarStyle: { backgroundColor: palette.surface, borderTopColor: palette.border },
        sceneStyle: { backgroundColor: palette.background },
      }}
    >
      <Tabs.Screen name="home" options={{ title: t("home"), tabBarIcon: icon("shield-checkmark-outline") }} />
      <Tabs.Screen
        name="businesses"
        options={{
          title: t("businesses"),
          tabBarIcon: icon("business-outline"),
          href: can("businesses.read") ? undefined : null,
        }}
      />
      <Tabs.Screen
        name="inbox"
        options={{
          title: t("inbox"),
          tabBarIcon: icon("mail-outline"),
          href: can("inbox.manage") ? undefined : null,
        }}
      />
      <Tabs.Screen name="me" options={{ title: t("me"), tabBarIcon: icon("person-outline") }} />
    </Tabs>
  );
}
