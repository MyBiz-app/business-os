import type { components } from "@business-os/api-client";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";
import { useTranslations } from "use-intl";

import { Button, Card, ErrorText, Field, Heading, Screen, styles } from "@/components/ui";
import { ApiError, apiClient, assetUrl, unwrap } from "@/lib/api";
import { brandPalette } from "@/lib/brand";
import { useBusiness } from "@/providers/business-provider";
import { useTheme } from "@/providers/theme-provider";

type Profile = components["schemas"]["BusinessProfile"];

const normalize = (value: string) => value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 16);

/** Join a business with the code it shares (typed, or from a mybiz://join?code=… link). */
export default function Join() {
  const t = useTranslations("client.join");
  const { palette: basePalette } = useTheme();
  const { join, businesses } = useBusiness();
  const params = useLocalSearchParams<{ code?: string }>();
  const [code, setCode] = useState(normalize(params.code ?? ""));
  const [profile, setProfile] = useState<Profile | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const palette = brandPalette(basePalette, profile?.primary_color);

  const lookUp = async (value: string) => {
    if (value.length < 4) return setError(t("unknownCode"));
    setBusy(true);
    setError(null);
    try {
      setProfile(
        unwrap(await apiClient().GET("/public/businesses/{code}", { params: { path: { code: value } } })),
      );
    } catch (caught) {
      setError(caught instanceof ApiError && caught.status === 404 ? t("unknownCode") : t("generic"));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (params.code) void lookUp(normalize(params.code));
    // Only for a code that arrived in the link.
  }, [params.code]);

  const confirmJoin = async () => {
    setBusy(true);
    setError(null);
    try {
      await join(code);
      router.replace("/home");
    } catch {
      setError(t("generic"));
      setBusy(false);
    }
  };

  const logo = assetUrl(profile?.logo_url);

  return (
    <Screen palette={palette}>
      <Heading palette={palette}>{t("title")}</Heading>
      {profile ? (
        <>
          <Card palette={palette}>
            <View style={local.brand}>
              {logo ? (
                <Image source={{ uri: logo }} style={local.logo} accessibilityIgnoresInvertColors />
              ) : (
                <View style={[local.logo, { backgroundColor: palette.primary }]} />
              )}
              <Text style={[local.name, { color: palette.foreground }]}>{profile.name}</Text>
            </View>
            <Text style={[styles.muted, { color: palette.muted }]}>{t("preview")}</Text>
          </Card>
          <ErrorText message={error} palette={palette} />
          <Button label={t("joinButton", { name: profile.name })} palette={palette} busy={busy} onPress={() => void confirmJoin()} />
          <Button label={t("otherCode")} variant="secondary" palette={palette} onPress={() => setProfile(null)} />
        </>
      ) : (
        <>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("subtitle")}</Text>
          <Field
            label={t("code")}
            palette={palette}
            value={code}
            onChangeText={(value) => setCode(normalize(value))}
            autoCapitalize="characters"
            autoCorrect={false}
            style={local.code}
            onSubmitEditing={() => void lookUp(code)}
          />
          <ErrorText message={error} palette={palette} />
          <Button label={t("continue")} palette={palette} busy={busy} onPress={() => void lookUp(code)} />
          {businesses && businesses.length > 0 && (
            <Button label={t("back")} variant="secondary" palette={palette} onPress={() => router.replace("/home")} />
          )}
        </>
      )}
    </Screen>
  );
}

const local = StyleSheet.create({
  brand: { flexDirection: "row", alignItems: "center", gap: 12 },
  logo: { width: 56, height: 56, borderRadius: 14 },
  name: { fontSize: 22, fontWeight: "700", flexShrink: 1, textAlign: "left" },
  code: { fontSize: 22, letterSpacing: 4, writingDirection: "ltr", textAlign: "center" },
});
