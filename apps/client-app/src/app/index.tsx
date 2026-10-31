import { Redirect } from "expo-router";
import { useEffect, useState } from "react";
import { Platform, View } from "react-native";

import { areaHome } from "@business-os/app-kit/lib/areas";
import { introSeen } from "@business-os/app-kit/lib/intro";
import { useAreas } from "@/providers/area-provider";
import { useSession } from "@business-os/app-kit/providers/session-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";
import { Spinner } from "@business-os/app-kit/components/spinner";
import { LoadError } from "@business-os/app-kit/components/ui";

/** Sends the person where they belong: sign in, join a business, or the area they used last. */
export default function Gate() {
  const { session, loading, mfaPending } = useSession();
  const { areas, active, failed, retry } = useAreas();
  const { palette } = useTheme();
  // The first-run intro is for phones; the web (and its deep links and checks) goes straight to sign-in.
  const [intro, setIntro] = useState<"checking" | "seen" | "unseen">(Platform.OS === "web" ? "seen" : "checking");
  useEffect(() => {
    if (intro === "checking") void introSeen().then((seen) => setIntro(seen ? "seen" : "unseen"));
  }, [intro]);

  const wait = (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: palette.background }}>
      <Spinner color={palette.primary} />
    </View>
  );

  if (!loading && (!session || mfaPending)) {
    if (intro === "checking") return wait;
    return <Redirect href={!session && intro === "unseen" ? "/intro" : "/sign-in"} />;
  }
  if (areas && areas.length === 0) return <Redirect href="/join" />;
  if (active) return <Redirect href={areaHome(active)} />;
  // The businesses could not be loaded (a sleeping server, no signal): say so and offer a retry;
  // it is not the same as having no business, which goes to the join screen above.
  if (failed) {
    return (
      <View style={{ flex: 1, justifyContent: "center", padding: 24, backgroundColor: palette.background }}>
        <LoadError palette={palette} onRetry={retry} />
      </View>
    );
  }
  return wait;
}
