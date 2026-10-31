import type { components } from "@business-os/api-client";
import { Redirect, router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import Ionicons from "@expo/vector-icons/Ionicons";
import { Image, Linking, Pressable, StyleSheet, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useTranslations } from "use-intl";

import { AddressPicker } from "@business-os/app-kit/components/address-picker";
import { AuthCard, AuthShell } from "@business-os/app-kit/components/auth-shell";
import { DepthLogo } from "@business-os/app-kit/components/launch-splash";
import { FadeIn } from "@business-os/app-kit/components/motion";
import { Button, Card, ErrorText, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { supabase } from "@business-os/app-kit/lib/supabase";
import { EMPTY_ADDRESS } from "@business-os/app-kit/lib/address";
import { ApiError, apiClient, assetUrl, unwrap } from "@business-os/app-kit/lib/api";
import { brandPalette } from "@business-os/app-kit/lib/brand";
import { JoinScanner } from "@/components/join-scanner";
import { JoinWelcome } from "@/components/join-welcome";
import { useBusiness } from "@/providers/business-provider";
import { useSession } from "@business-os/app-kit/providers/session-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";
import { radius } from "@business-os/app-kit/lib/theme";

type Profile = components["schemas"]["BusinessProfile"];

/** Join codes are 8 characters long. */
const CODE_LENGTH = 8;

const normalize = (value: string) => value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 16);

/** Join a business with the code it shares (typed, or from a mybiz://join?code=… link). */
export default function Join() {
  const t = useTranslations("client.join");
  const { palette: basePalette } = useTheme();
  const { join, businesses, refresh } = useBusiness();
  const { session, loading } = useSession();
  const params = useLocalSearchParams<{ code?: string }>();
  const [code, setCode] = useState(normalize(params.code ?? ""));
  const [profile, setProfile] = useState<Profile | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The name the business will see; taken from another business the person already joined.
  const known = businesses?.[0];
  const [firstName, setFirstName] = useState(known?.first_name ?? "");
  const [lastName, setLastName] = useState(known?.last_name ?? "");
  // Optional: "which city are you from?" helps the business see where its community lives.
  const [city, setCity] = useState(EMPTY_ADDRESS);
  const tAddress = useTranslations("address");
  // Marketing messages are opt-in: off until the person ticks it.
  const [marketing, setMarketing] = useState(false);
  // Set once joined: the next step shows the business's cancellation rules before the home screen.
  const [joinedId, setJoinedId] = useState<string | null>(null);
  const palette = brandPalette(basePalette, profile?.primary_color);
  const [scanning, setScanning] = useState(false);

  const lookUp = async (value: string) => {
    if (value.length === 0) return setError(t("codeRequired"));
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.code]);

  const pick = (value: string) => {
    const next = normalize(value);
    setCode(next);
    setScanning(false);
    void lookUp(next);
  };

  const confirmJoin = async () => {
    if (!firstName.trim()) return setError(t("nameRequired"));
    setBusy(true);
    setError(null);
    try {
      const joined = await join(code);
      await apiClient().PATCH("/client/profile", {
        params: { header: { "X-Tenant-Id": joined.id } },
        body: { first_name: firstName.trim(), last_name: lastName.trim() || joined.last_name || null, phone: joined.phone ?? known?.phone ?? null, ...(city.cityCode !== null ? { city_code: city.cityCode } : {}) },
      }).then(unwrap);
      // A failure here must not undo the join; the person can still choose on their profile.
      if (marketing) await apiClient().PUT("/me/marketing-consent", { body: { consent: true, source: "app_join" } }).catch(() => undefined);
      await refresh();
      setJoinedId(joined.id);
      setBusy(false);
    } catch {
      setError(t("generic"));
      setBusy(false);
    }
  };

  const logo = assetUrl(profile?.logo_url);
  // A join link opened before signing in: sign in first, then come back with the code.
  if (!loading && !session) {
    return <Redirect href={params.code ? { pathname: "/sign-in", params: { code: normalize(params.code) } } : "/sign-in"} />;
  }

  if (joinedId) return <JoinWelcome name={profile?.name ?? ""} tenantId={joinedId} palette={palette} />;

  // A person with no business yet gets a welcome (the branded sign-in frame); others keep the plain join page.
  const firstTime = businesses !== null && businesses !== undefined && businesses.length === 0 && !profile;
  const entryForm = (
    <>
          {firstTime ? null : <Text style={[styles.muted, { color: palette.muted }]}>{t("subtitle")}</Text>}
          {/* The business gives its QR or its code: scanning is the quick way, so it comes first. */}
          <Button label={t("scan")} palette={palette} onPress={() => setScanning(true)} />
          <Text style={[styles.muted, { color: palette.muted, textAlign: "center" }]}>{t("orType")}</Text>
          <Field
            label={t("code")}
            palette={palette}
            value={code}
            onChangeText={(value) => {
              const next = normalize(value);
              setCode(next);
              // A whole code (a pasted or an autofilled one) is looked up at once.
              if (next.length === CODE_LENGTH && next !== code) void lookUp(next);
            }}
            autoCapitalize="characters"
            autoCorrect={false}
            style={local.code}
            returnKeyType="go"
            onSubmitEditing={() => void lookUp(code)}
          />
          <ErrorText message={error} palette={palette} />
          <Button label={t("continue")} variant="secondary" palette={palette} busy={busy} onPress={() => void lookUp(code)} />
          <Text style={[styles.muted, { color: palette.muted, textAlign: "center" }]}>{t("noCode")}</Text>
          <JoinScanner visible={scanning} palette={palette} onCode={pick} onClose={() => setScanning(false)} />
          {businesses && businesses.length > 0 && (
            <Button label={t("back")} variant="secondary" palette={palette} onPress={() => router.replace("/home")} />
          )}
          {firstTime ? (
            <Button label={t("otherAccount")} variant="quiet" palette={palette} onPress={() => void supabase.auth.signOut().then(() => router.replace("/sign-in"))} />
          ) : null}
    </>
  );

  if (firstTime) {
    return (
      <AuthShell>
        <FadeIn index={0} style={{ alignItems: "center", gap: 6 }}>
          <DepthLogo size={0.8} />
          <Heading palette={palette}>{t("welcomeTitle")}</Heading>
          <Text style={[styles.muted, { color: palette.muted, textAlign: "center" }]}>{t("welcomeSubtitle")}</Text>
        </FadeIn>
        <AuthCard>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("subtitle")}</Text>
          {entryForm}
        </AuthCard>
      </AuthShell>
    );
  }

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
          {profile.client_app && (
            <>
              <Field label={t("firstName")} palette={palette} value={firstName} onChangeText={setFirstName} autoComplete="given-name" textContentType="givenName" />
              <Field label={t("lastName")} palette={palette} value={lastName} onChangeText={setLastName} autoComplete="family-name" textContentType="familyName" />
              <AddressPicker palette={palette} value={city} onChange={setCity} cityOnly cityLabel={tAddress("fromCity")} cityHint={tAddress("fromCityHint")} />
              <Pressable
                role="checkbox"
                aria-checked={marketing}
                accessibilityLabel={t("marketing")}
                onPress={() => setMarketing((on) => !on)}
                style={local.consent}
              >
                <View style={[local.box, { borderColor: marketing ? palette.primary : palette.border, backgroundColor: marketing ? palette.primary : palette.surface }]}>
                  {marketing ? <Ionicons name="checkmark" size={18} color={palette.onPrimary} /> : null}
                </View>
                <Text style={[local.consentText, { color: palette.foreground }]}>{t("marketing")}</Text>
              </Pressable>
              <Text style={[styles.muted, { color: palette.muted }]}>{t("legal")}</Text>
            </>
          )}
          <ErrorText message={error} palette={palette} />
          {profile.client_app ? (
            <Button label={t("joinButton", { name: profile.name })} palette={palette} busy={busy} onPress={() => void confirmJoin()} />
          ) : (
            <Text style={[styles.muted, { color: palette.foreground }]}>{t("noApp")}</Text>
          )}
          {profile.website_url ? (
            <Button label={t("visitSite")} variant="secondary" palette={palette} onPress={() => void Linking.openURL(profile.website_url!)} />
          ) : null}
          <Button label={t("otherCode")} variant="secondary" palette={palette} onPress={() => setProfile(null)} />
        </>
      ) : (
        entryForm
      )}
    </Screen>
  );
}

const local = StyleSheet.create({
  consent: { flexDirection: "row", alignItems: "center", gap: 12, minHeight: 44 },
  box: { width: 26, height: 26, borderRadius: radius.sm, borderWidth: 2, alignItems: "center", justifyContent: "center" },
  consentText: { flex: 1, fontSize: 15 },
  brand: { flexDirection: "row", alignItems: "center", gap: 12 },
  logo: { width: 56, height: 56, borderRadius: radius.control },
  name: { fontSize: 20, fontWeight: "600", flexShrink: 1, textAlign: "left" },
  code: { fontSize: 20, letterSpacing: 4, writingDirection: "ltr", textAlign: "center" },
});
