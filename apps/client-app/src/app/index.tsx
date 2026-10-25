import { Redirect } from "expo-router";
import { View } from "react-native";

import { areaHome } from "@business-os/app-kit/lib/areas";
import { useAreas } from "@/providers/area-provider";
import { useSession } from "@business-os/app-kit/providers/session-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";
import { Spinner } from "@business-os/app-kit/components/spinner";

/** Sends the person where they belong: sign in, join a business, or the area they used last. */
export default function Gate() {
  const { session, loading, mfaPending } = useSession();
  const { areas, active } = useAreas();
  const { palette } = useTheme();

  if (!loading && (!session || mfaPending)) return <Redirect href="/sign-in" />;
  if (areas && areas.length === 0) return <Redirect href="/join" />;
  if (active) return <Redirect href={areaHome(active)} />;
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: palette.background }}>
      <Spinner color={palette.primary} />
    </View>
  );
}
