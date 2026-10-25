import { Redirect, Tabs } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { tabIcon, useTabScreenOptions } from "@business-os/app-kit/components/tab-options";

import { useBusiness } from "@/providers/business-provider";
import { InboxProvider, useInbox } from "@/providers/inbox-provider";
import { useSession } from "@business-os/app-kit/providers/session-provider";
import { Spinner } from "@business-os/app-kit/components/spinner";

/** The client app's bottom tabs, in the selected business's brand color. */
export default function TabsLayout() {
  const { session, loading } = useSession();
  const { businesses, business, palette } = useBusiness();

  if (!loading && !session) return <Redirect href="/sign-in" />;
  if (businesses && !business) return <Redirect href="/join" />;
  if (!business) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: palette.background }}>
        <Spinner color={palette.primary} />
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
  const screenOptions = useTabScreenOptions(palette);
  const icon = (name: Parameters<typeof tabIcon>[0]) => tabIcon(name, palette);
  const { inbox } = useInbox();
  const unread = inbox?.unread ?? 0;

  return (
    <Tabs
      screenOptions={screenOptions}
    >
      <Tabs.Screen name="home" options={{ title: t("home"), tabBarIcon: icon("home") }} />
      {/* "My businesses" is reached from the business strip, not from the tab bar. */}
      <Tabs.Screen name="all" options={{ href: null }} />
      <Tabs.Screen
        name="schedule"
        options={{
          title: t("book"),
          tabBarIcon: icon("calendar"),
        }}
      />
      <Tabs.Screen name="bookings" options={{ title: t("mine"), tabBarIcon: icon("ticket") }} />
      <Tabs.Screen
        name="updates"
        options={{
          title: t("updates"),
          tabBarIcon: icon("notifications"),
          tabBarBadge: unread > 0 ? (unread > 9 ? "9+" : unread) : undefined,
          tabBarAccessibilityLabel: unread > 0 ? t("updatesUnread", { count: unread }) : t("updates"),
          tabBarBadgeStyle: { backgroundColor: palette.primary, color: palette.onPrimary },
        }}
      />
      <Tabs.Screen name="profile" options={{ title: t("profile"), tabBarIcon: icon("person") }} />
    </Tabs>
  );
}
