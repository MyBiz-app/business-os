import { Redirect, Tabs } from "expo-router";
import { ActivityIndicator, View } from "react-native";
import { useTranslations } from "use-intl";

import { tabIcon, useTabScreenOptions } from "@business-os/app-kit/components/tab-options";

import { termsFor } from "@business-os/app-kit/lib/vertical";
import { useAreas } from "@/providers/area-provider";
import { AiHeader } from "@/components/ai-header";
import { useStaff } from "@/providers/staff-provider";
import { useSession } from "@business-os/app-kit/providers/session-provider";

/** The business app's tabs, in the business's own brand color. Tabs follow permissions. */
export default function TabsLayout() {
  const { session, loading } = useSession();
  const { tenant, closedBusiness, palette, can } = useStaff();
  const { active } = useAreas();
  const screenOptions = useTabScreenOptions(palette);
  const icon = (name: Parameters<typeof tabIcon>[0]) => tabIcon(name, palette);
  const t = useTranslations("business.tabs");
  const tTerms = useTranslations("terms");

  if (!loading && !session) return <Redirect href="/sign-in" />;
  if (active && active.kind !== "business") return <Redirect href="/" />;
  if (closedBusiness) return <Redirect href="/closed" />;
  if (!tenant) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: palette.background }}>
        <ActivityIndicator color={palette.primary} />
      </View>
    );
  }

  const crm = tenant.modules.includes("crm");

  return (
    <View style={{ flex: 1 }}>
    <AiHeader />
    <Tabs
      screenOptions={screenOptions}
    >
      <Tabs.Screen name="today" options={{ title: t("today"), tabBarIcon: icon("today") }} />
      <Tabs.Screen
        name="clients"
        options={{
          title: tTerms(`${termsFor(tenant)}.clients`),
          tabBarIcon: icon("people"),
          href: can("clients.read") ? undefined : null,
        }}
      />
      <Tabs.Screen
        name="inbox"
        options={{
          title: crm ? t("leads") : t("messages"),
          tabBarIcon: icon(crm ? "funnel" : "chatbubbles"),
          href: can("clients.read") && (crm || tenant.modules.includes("whatsapp")) ? undefined : null,
        }}
      />
      <Tabs.Screen
        name="numbers"
        options={{
          title: t("numbers"),
          tabBarIcon: icon("stats-chart"),
          href: can("reports.read") ? undefined : null,
        }}
      />
      <Tabs.Screen name="me" options={{ title: t("me"), tabBarIcon: icon("person") }} />
    </Tabs>
    </View>
  );
}
