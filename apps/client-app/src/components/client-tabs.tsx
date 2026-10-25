import { Tabs } from "expo-router";
import { useTranslations } from "use-intl";

import { tabIcon, useTabScreenOptions } from "@business-os/app-kit/components/tab-options";
import { haptics } from "@business-os/app-kit/lib/haptics";

import { useBusiness } from "@/providers/business-provider";
import { useInbox } from "@/providers/inbox-provider";

/** The client app's five tabs, as the JS tab bar (web and Android; iOS uses `client-tabs.ios.tsx`). */
export function ClientTabs() {
  const t = useTranslations("client.tabs");
  const { palette } = useBusiness();
  const screenOptions = useTabScreenOptions(palette);
  const icon = (name: Parameters<typeof tabIcon>[0]) => tabIcon(name, palette);
  const { inbox } = useInbox();
  const unread = inbox?.unread ?? 0;

  return (
    <Tabs screenOptions={screenOptions} screenListeners={{ tabPress: () => haptics.select() }}>
      <Tabs.Screen name="home" options={{ title: t("home"), tabBarIcon: icon("home") }} />
      <Tabs.Screen name="schedule" options={{ title: t("book"), tabBarIcon: icon("calendar") }} />
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
