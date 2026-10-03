import { Redirect } from "expo-router";
import { ActivityIndicator, View } from "react-native";

import { useBusiness } from "@/providers/business-provider";
import { useSession } from "@/providers/session-provider";
import { useTheme } from "@/providers/theme-provider";

/** Sends the user where they belong: sign in, join a business, or the business's home. */
export default function Gate() {
  const { session, loading } = useSession();
  const { businesses } = useBusiness();
  const { palette } = useTheme();

  if (!loading && !session) return <Redirect href="/sign-in" />;
  if (businesses && businesses.length === 0) return <Redirect href="/join" />;
  if (businesses) return <Redirect href="/home" />;
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: palette.background }}>
      <ActivityIndicator color={palette.primary} />
    </View>
  );
}
