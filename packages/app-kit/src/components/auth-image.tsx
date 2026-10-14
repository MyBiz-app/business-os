import { useEffect, useState } from "react";
import { Image, type ImageStyle, type StyleProp } from "react-native";

import { API_URL } from "../lib/api";
import { supabase } from "../lib/supabase";

/** Reads a blob as a data URI (works on native and the web, unlike a blob: URL on native). */
function readAsDataUri(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

/** A picture that the API only serves to the signed-in person (their own avatar). */
export function AuthImage({ path, style, label }: { path: string | null | undefined; style: StyleProp<ImageStyle>; label?: string }) {
  const [uri, setUri] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    setUri(null);
    if (!path) return;
    void (async () => {
      try {
        const { data } = await supabase.auth.getSession();
        const response = await fetch(`${API_URL}${path}`, {
          headers: data.session ? { Authorization: `Bearer ${data.session.access_token}` } : {},
        });
        if (!response.ok) return;
        const next = await readAsDataUri(await response.blob());
        if (!cancelled) setUri(next);
      } catch {
        // No picture: the caller shows the initials instead.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [path]);
  if (!uri) return null;
  return <Image source={{ uri }} style={style} accessibilityLabel={label} accessibilityIgnoresInvertColors />;
}
