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

// One request per picture however many places show it (the same person sits in many class blocks).
// Addresses carry a version, so a changed picture has a new address.
const pictures = new Map<string, Promise<string | null>>();
const MAX_PICTURES = 200;

function fetchPicture(path: string): Promise<string | null> {
  let request = pictures.get(path);
  if (!request) {
    if (pictures.size >= MAX_PICTURES) pictures.delete(pictures.keys().next().value as string);
    request = (async () => {
      try {
        const { data } = await supabase.auth.getSession();
        const response = await fetch(`${API_URL}${path}`, {
          headers: data.session ? { Authorization: `Bearer ${data.session.access_token}` } : {},
        });
        return response.ok ? await readAsDataUri(await response.blob()) : null;
      } catch {
        return null;
      }
    })();
    pictures.set(path, request);
    void request.then((uri) => uri === null && pictures.delete(path));
  }
  return request;
}

/** Drop the pictures kept in memory (another person signed in). */
export function forgetPictures() {
  pictures.clear();
}

/** A picture that the API only serves to the signed-in person (their own avatar). */
export function AuthImage({ path, style, label }: { path: string | null | undefined; style: StyleProp<ImageStyle>; label?: string }) {
  const [uri, setUri] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    setUri(null);
    if (!path) return;
    // No picture: the caller shows the initials instead.
    void fetchPicture(path).then((next) => !cancelled && setUri(next));
    return () => {
      cancelled = true;
    };
  }, [path]);
  if (!uri) return null;
  return <Image source={{ uri }} style={style} accessibilityLabel={label} accessibilityIgnoresInvertColors />;
}
