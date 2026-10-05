import { Redirect } from "expo-router";
import { ActivityIndicator, View } from "react-native";

import { useSession } from "@business-os/app-kit/providers/session-provider";
import { useStaff } from "@/providers/staff-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

/** Sends the person to sign in, the "not on the team" note, or the console's home. */
export default function Gate() {
  const { session, loading } = useSession();
  const { onTeam } = useStaff();
  const { palette } = useTheme();

  if (!loading && !session) return <Redirect href="/sign-in" />;
  if (onTeam === false) return <Redirect href="/not-staff" />;
  if (onTeam) return <Redirect href="/home" />;
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: palette.background }}>
      <ActivityIndicator color={palette.primary} />
    </View>
  );
}
