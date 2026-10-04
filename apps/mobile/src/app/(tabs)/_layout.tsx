import Ionicons from "@expo/vector-icons/Ionicons";
import { Redirect, Tabs } from "expo-router";
import { ActivityIndicator, type ColorValue, View } from "react-native";
import { useTranslations } from "use-intl";

import { useBusiness } from "@/providers/business-provider";
import { InboxProvider, useInbox } from "@/providers/inbox-provider";
import { useSession } from "@/providers/session-provider";

type IconName = React.ComponentProps<typeof Ionicons>["name"];

const icon =
  (name: IconName) =>
  ({ color, size }: { color: ColorValue; size: number }) => <Ionicons name={name} color={color as string} size={size} />;

/** The client app's bottom tabs, in the selected business's brand color. */
export default function TabsLayout() {
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
    <InboxProvider>
      <BusinessTabs />
    </InboxProvider>
  );
}

function BusinessTabs() {
  const t = useTranslations("client.tabs");
  const { palette } = useBusiness();
  const { inbox } = useInbox();
  const unread = inbox?.unread ?? 0;

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
      <Tabs.Screen
        name="updates"
        options={{
          title: t("updates"),
          tabBarIcon: icon("notifications-outline"),
          tabBarBadge: unread > 0 ? (unread > 9 ? "9+" : unread) : undefined,
          tabBarAccessibilityLabel: unread > 0 ? t("updatesUnread", { count: unread }) : t("updates"),
          tabBarBadgeStyle: { backgroundColor: palette.primary, color: palette.onPrimary },
        }}
      />
      <Tabs.Screen name="profile" options={{ title: t("profile"), tabBarIcon: icon("person-outline") }} />
    </Tabs>
  );
}
