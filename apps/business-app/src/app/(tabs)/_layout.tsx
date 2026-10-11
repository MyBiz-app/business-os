import Ionicons from "@expo/vector-icons/Ionicons";
import { Redirect, Tabs } from "expo-router";
import { ActivityIndicator, type ColorValue, View } from "react-native";
import { useTranslations } from "use-intl";

import { termsFor } from "@business-os/app-kit/lib/vertical";
import { useBusiness } from "@/providers/business-provider";
import { useSession } from "@business-os/app-kit/providers/session-provider";

type IconName = React.ComponentProps<typeof Ionicons>["name"];

const icon =
  (name: IconName) =>
  ({ color, size }: { color: ColorValue; size: number }) => <Ionicons name={name} color={color as string} size={size} />;

/** The business app's tabs, in the business's own brand color. Tabs follow permissions. */
export default function TabsLayout() {
  const { session, loading } = useSession();
  const { memberships, tenant, palette, can } = useBusiness();
  const t = useTranslations("business.tabs");
  const tTerms = useTranslations("terms");

  if (!loading && !session) return <Redirect href="/sign-in" />;
  if (memberships && memberships.length === 0) return <Redirect href="/no-business" />;
  if (!tenant) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: palette.background }}>
        <ActivityIndicator color={palette.primary} />
      </View>
    );
  }

  const crm = tenant.modules.includes("crm");

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
      <Tabs.Screen name="today" options={{ title: t("today"), tabBarIcon: icon("today-outline") }} />
      <Tabs.Screen
        name="clients"
        options={{
          title: tTerms(`${termsFor(tenant)}.clients`),
          tabBarIcon: icon("people-outline"),
          href: can("clients.read") ? undefined : null,
        }}
      />
      <Tabs.Screen
        name="inbox"
        options={{
          title: crm ? t("leads") : t("messages"),
          tabBarIcon: icon(crm ? "funnel-outline" : "chatbubbles-outline"),
          href: can("clients.read") && (crm || tenant.modules.includes("whatsapp")) ? undefined : null,
        }}
      />
      <Tabs.Screen
        name="numbers"
        options={{
          title: t("numbers"),
          tabBarIcon: icon("stats-chart-outline"),
          href: can("reports.read") ? undefined : null,
        }}
      />
      <Tabs.Screen name="me" options={{ title: t("me"), tabBarIcon: icon("person-outline") }} />
    </Tabs>
  );
}
