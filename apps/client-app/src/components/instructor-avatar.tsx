import { useEffect, useState } from "react";
import { Image } from "react-native";

import { Avatar } from "@business-os/app-kit/components/rows";
import { assetUrl } from "@business-os/app-kit/lib/api";
import { supabase } from "@business-os/app-kit/lib/supabase";
import type { Palette } from "@business-os/app-kit/lib/theme";

type Props = { name: string; path: string | null | undefined; palette: Palette; size?: number };

/** An instructor's picture (members only, so it is fetched with the sign-in token); initials until it loads or when they have none. */
export function InstructorAvatar({ name, path, palette, size = 28 }: Props) {
  const uri = assetUrl(path);
  const [token, setToken] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!uri) return;
    void supabase.auth.getSession().then(({ data }) => setToken(data.session?.access_token ?? null));
  }, [uri]);
  if (!uri || !token || failed) return <Avatar name={name} palette={palette} size={size} />;
  return (
    <Image
      source={{ uri, headers: { Authorization: `Bearer ${token}` } }}
      accessible={false}
      accessibilityIgnoresInvertColors
      onError={() => setFailed(true)}
      style={{ width: size, height: size, borderRadius: size / 2 }}
    />
  );
}
