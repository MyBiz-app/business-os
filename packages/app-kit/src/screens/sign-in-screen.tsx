import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { View } from "react-native";
import { Text } from "../components/text";
import { ThemeToggle } from "../components/theme-toggle";
import { ltr } from "../components/ltr";
import { useTranslations } from "use-intl";

import { Button, ErrorText, Field, Heading, Screen, styles } from "../components/ui";
import { SUPABASE_KEY, SUPABASE_URL } from "../lib/env";
import { availableChannels, OTP_LENGTH, toE164, type OtpChannel } from "../lib/otp";
import { supabase } from "../lib/supabase";
import { useTheme } from "../providers/theme-provider";

// WhatsApp codes also need the SMS provider; this switch keeps the option hidden until the
// provider's WhatsApp sender is approved.
const WHATSAPP_ON = process.env.EXPO_PUBLIC_AUTH_WHATSAPP === "true";
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Which ways of getting a code the Supabase project offers (email always; phone once an SMS provider is on). */
function useChannels(): OtpChannel[] {
  const [channels, setChannels] = useState<OtpChannel[]>(["email"]);
  useEffect(() => {
    let live = true;
    fetch(`${SUPABASE_URL}/auth/v1/settings`, { headers: { apikey: SUPABASE_KEY } })
      .then((response) => (response.ok ? response.json() : null))
      .then((settings) => live && setChannels(availableChannels(settings, WHATSAPP_ON)))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);
  return channels;
}

/** Passwordless sign-in, shared by the three apps: the user gets a 6-digit code by email (new
 * users are signed up), or by SMS / WhatsApp on the phone number saved on their account when the
 * project offers it. Each app's `sign-in` route re-exports it. */
export function SignInScreen() {
  const t = useTranslations("client.signIn");
  const { palette } = useTheme();
  // Set when a join link sent the user here first.
  const { code: joinCode } = useLocalSearchParams<{ code?: string }>();
  const channels = useChannels();
  const [channel, setChannel] = useState<OtpChannel>("email");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendCode = async () => {
    setError(null);
    if (channel === "email") {
      const address = email.trim().toLowerCase();
      if (!EMAIL.test(address)) return setError(t("invalidEmail"));
      setBusy(true);
      const { error: failed } = await supabase.auth.signInWithOtp({ email: address, options: { shouldCreateUser: true } });
      setBusy(false);
      if (failed) return setError(failed.status === 429 ? t("tooMany") : t("generic"));
      setSentTo(address);
    } else {
      const number = toE164(phone);
      if (!number) return setError(t("invalidPhone"));
      setBusy(true);
      // Only people who already verified this number on their account can sign in with it.
      const { error: failed } = await supabase.auth.signInWithOtp({ phone: number, options: { shouldCreateUser: false, channel } });
      setBusy(false);
      if (failed) return setError(failed.status === 429 ? t("tooMany") : failed.code === "otp_disabled" || failed.code === "user_not_found" ? t("unknownPhone") : t("generic"));
      setSentTo(number);
    }
    setCode("");
  };

  const verify = async () => {
    if (!sentTo) return;
    setBusy(true);
    setError(null);
    const { error: failed } = await supabase.auth.verifyOtp(
      channel === "email" ? { email: sentTo, token: code.trim(), type: "email" } : { phone: sentTo, token: code.trim(), type: "sms" },
    );
    setBusy(false);
    if (failed) return setError(t("invalidCode"));
    router.replace(joinCode ? { pathname: "/join", params: { code: joinCode } } : "/");
  };

  return (
    <Screen palette={palette}>
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <View style={{ flex: 1 }}>
          <Heading palette={palette}>{t("title")}</Heading>
        </View>
        <ThemeToggle />
      </View>
      {sentTo ? (
        <>
          <Text style={[styles.muted, { color: palette.muted }]}>{t(channel === "email" ? "codeSent" : "codeSentPhone", { target: ltr(sentTo) })}</Text>
          <Field
            label={t(channel === "email" ? "code" : "codePhone")}
            palette={palette}
            value={code}
            onChangeText={(value) => setCode(value.replace(/\D/g, "").slice(0, OTP_LENGTH))}
            dir="ltr"
            keyboardType="number-pad"
            autoComplete="one-time-code"
            textContentType="oneTimeCode"
            autoFocus
            onSubmitEditing={() => void verify()}
          />
          <ErrorText message={error} palette={palette} />
          <Button label={t("verify")} palette={palette} busy={busy} disabled={code.length < OTP_LENGTH} onPress={() => void verify()} />
          <Button label={t(channel === "email" ? "changeEmail" : "changePhone")} variant="secondary" palette={palette} onPress={() => setSentTo(null)} />
        </>
      ) : (
        <>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("subtitle")}</Text>
          {channels.length > 1 && (
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
              {channels.map((option) => (
                <Button
                  key={option}
                  label={t(`channel.${option}`)}
                  variant={channel === option ? "primary" : "secondary"}
                  palette={palette}
                  onPress={() => {
                    setChannel(option);
                    setError(null);
                  }}
                />
              ))}
            </View>
          )}
          {channel === "email" ? (
            <Field
              label={t("email")}
              palette={palette}
              value={email}
              onChangeText={setEmail}
              dir="ltr"
              keyboardType="email-address"
              autoCapitalize="none"
              autoComplete="email"
              textContentType="emailAddress"
              onSubmitEditing={() => void sendCode()}
            />
          ) : (
            <Field
              label={t("phone")}
              palette={palette}
              value={phone}
              onChangeText={setPhone}
              dir="ltr"
              keyboardType="phone-pad"
              autoComplete="tel"
              textContentType="telephoneNumber"
              onSubmitEditing={() => void sendCode()}
            />
          )}
          <ErrorText message={error} palette={palette} />
          <Button label={t("sendCode")} palette={palette} busy={busy} onPress={() => void sendCode()} />
        </>
      )}
    </Screen>
  );
}
