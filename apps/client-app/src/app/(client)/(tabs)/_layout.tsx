import { Redirect, Tabs } from "expo-router";
import { ActivityIndicator, View } from "react-native";
import { useTranslations } from "use-intl";

import { tabIcon, useTabScreenOptions } from "@business-os/app-kit/components/tab-options";

import { termsFor } from "@business-os/app-kit/lib/vertical";
import { useBusiness } from "@/providers/business-provider";
import { InboxProvider, useInbox } from "@/providers/inbox-provider";
import { useSession } from "@business-os/app-kit/providers/session-provider";

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
  const { palette, business } = useBusiness();
  const screenOptions = useTabScreenOptions(palette);
  const icon = (name: Parameters<typeof tabIcon>[0]) => tabIcon(name, palette);
  const tTerms = useTranslations("terms");
  const { inbox } = useInbox();
  const unread = inbox?.unread ?? 0;

  return (
    <Tabs
      screenOptions={screenOptions}
    >
      <Tabs.Screen name="home" options={{ title: t("home"), tabBarIcon: icon("home") }} />
      {/* "All mine" is reached from the business strip, not from the tab bar. */}
      <Tabs.Screen name="all" options={{ href: null }} />
      <Tabs.Screen
        name="schedule"
        options={{
          title: business ? tTerms(`${termsFor(business)}.appTab`) : t("schedule"),
          tabBarIcon: icon("calendar"),
        }}
      />
      <Tabs.Screen name="bookings" options={{ title: t("bookings"), tabBarIcon: icon("checkmark-done") }} />
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
