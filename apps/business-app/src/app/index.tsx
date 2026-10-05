import { Redirect } from "expo-router";
import { ActivityIndicator, View } from "react-native";

import { useBusiness } from "@/providers/business-provider";
import { useSession } from "@/providers/session-provider";
import { useTheme } from "@/providers/theme-provider";

/** Sends the staff member where they belong: sign in, the "no business" note, or today. */
export default function Gate() {
  const { session, loading } = useSession();
  const { memberships, tenant } = useBusiness();
  const { palette } = useTheme();

  if (!loading && !session) return <Redirect href="/sign-in" />;
  if (memberships && memberships.length === 0) return <Redirect href="/no-business" />;
  if (tenant) return <Redirect href="/today" />;
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: palette.background }}>
      <ActivityIndicator color={palette.primary} />
    </View>
  );
}
