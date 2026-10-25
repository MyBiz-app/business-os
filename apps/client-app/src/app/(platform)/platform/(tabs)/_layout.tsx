import { Redirect, Tabs } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { tabIcon, useTabScreenOptions } from "@business-os/app-kit/components/tab-options";
import { haptics } from "@business-os/app-kit/lib/haptics";

import { useSession } from "@business-os/app-kit/providers/session-provider";
import { useAreas } from "@/providers/area-provider";
import { usePlatform } from "@/providers/platform-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";
import { Spinner } from "@business-os/app-kit/components/spinner";

/** The MyBiz team's tabs; each one appears only for someone whose permissions cover it. */
export default function TabsLayout() {
  const { session, loading } = useSession();
  const { active } = useAreas();
  const { onTeam, can } = usePlatform();
  const { palette } = useTheme();
  const screenOptions = useTabScreenOptions(palette);
  const icon = (name: Parameters<typeof tabIcon>[0]) => tabIcon(name, palette);
  const t = useTranslations("staffApp.tabs");

  if (!loading && !session) return <Redirect href="/sign-in" />;
  if (active && active.kind !== "platform") return <Redirect href="/" />;
  if (onTeam === false) return <Redirect href="/platform/not-team" />;
  if (!onTeam) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: palette.background }}>
        <Spinner color={palette.primary} />
      </View>
    );
  }

  return (
    <Tabs
      screenOptions={screenOptions}
      screenListeners={{ tabPress: () => haptics.select() }}
    >
      <Tabs.Screen name="home" options={{ title: t("home"), tabBarIcon: icon("shield-checkmark") }} />
      <Tabs.Screen
        name="businesses"
        options={{
          title: t("businesses"),
          tabBarIcon: icon("business"),
          href: can("businesses.read") ? undefined : null,
        }}
      />
      <Tabs.Screen
        name="inbox"
        options={{
          title: t("inbox"),
          tabBarIcon: icon("mail"),
          href: can("inbox.manage") ? undefined : null,
        }}
      />
      <Tabs.Screen
        name="ai"
        options={{
          title: t("ai"),
          tabBarIcon: icon("sparkles"),
          href: can("usage.read") ? undefined : null,
        }}
      />
      <Tabs.Screen name="me" options={{ title: t("me"), tabBarIcon: icon("person") }} />
    </Tabs>
  );
}
