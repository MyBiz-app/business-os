import Ionicons from "@expo/vector-icons/Ionicons";
import { Redirect, Tabs } from "expo-router";
import { ActivityIndicator, type ColorValue, View } from "react-native";
import { useTranslations } from "use-intl";

import { useBusiness } from "@/providers/business-provider";
import { useSession } from "@/providers/session-provider";

type IconName = React.ComponentProps<typeof Ionicons>["name"];

const icon =
  (name: IconName) =>
  ({ color, size }: { color: ColorValue; size: number }) => <Ionicons name={name} color={color as string} size={size} />;

/** The client app's bottom tabs, in the selected business's brand color. */
export default function TabsLayout() {
  const t = useTranslations("client.tabs");
  const { session, loading } = useSession();
  const { businesses, business, palette } = useBusiness();

  if (!loading && !session) return <Redirect href="/sign-in" />;
  if (businesses && !business) return <Redirect href="/join" />;
  if (!business) {
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
      <Tabs.Screen name="home" options={{ title: t("home"), tabBarIcon: icon("home-outline") }} />
      <Tabs.Screen name="schedule" options={{ title: t("schedule"), tabBarIcon: icon("calendar-outline") }} />
      <Tabs.Screen name="bookings" options={{ title: t("bookings"), tabBarIcon: icon("checkmark-done-outline") }} />
      <Tabs.Screen name="profile" options={{ title: t("profile"), tabBarIcon: icon("person-outline") }} />
    </Tabs>
  );
}
