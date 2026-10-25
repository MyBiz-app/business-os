import { Redirect } from "expo-router";
import { View } from "react-native";

import { ClientTabs } from "@/components/client-tabs";
import { useBusiness } from "@/providers/business-provider";
import { InboxProvider } from "@/providers/inbox-provider";
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
      <ClientTabs />
    </InboxProvider>
  );
}
