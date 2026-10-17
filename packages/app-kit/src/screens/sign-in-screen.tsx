import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { Text } from "../components/text";
import { ltr } from "../components/ltr";
import { useTranslations } from "use-intl";

import { AuthCard, AuthShell } from "../components/auth-shell";
import { DepthLogo } from "../components/launch-splash";
import { FadeIn } from "../components/motion";
import { OtpInput } from "../components/otp-input";
import { SegmentedControl } from "../components/segmented-control";
import { Button, ErrorText, Field, Heading, styles } from "../components/ui";
import { SUPABASE_KEY, SUPABASE_URL } from "../lib/env";
import { availableChannels, OTP_LENGTH, toE164, type OtpChannel } from "../lib/otp";
import { CODE_LENGTH, needsCodeStep } from "../lib/session-rules";
import { supabase } from "../lib/supabase";
import { useSession } from "../providers/session-provider";
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
  const tAuth = useTranslations("authUi");
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
  // The second step: a code from the authenticator app. Also when the app was reopened half-way.
  const tSecurity = useTranslations("security");
  const { mfaPending } = useSession();
  const [stepTwo, setStepTwo] = useState(false);
  const needsCode = stepTwo || mfaPending;

  const finish = () => router.replace(joinCode ? { pathname: "/join", params: { code: joinCode } } : "/");

  const verifyAuthenticator = async (entered = code) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    const { data: factors } = await supabase.auth.mfa.listFactors();
    // Any of the person's authenticators will do (a second device can be a backup).
    for (const factor of factors?.totp ?? []) {
      const { error: failed } = await supabase.auth.mfa.challengeAndVerify({ factorId: factor.id, code: entered.trim() });
      if (!failed) {
        setBusy(false);
        return finish();
      }
    }
    setBusy(false);
    setCode("");
    setError(tSecurity("errors.invalid_code"));
  };

  const sendCode = async () => {
    setError(null);
    if (channel === "email") {
      const address = email.trim().toLowerCase();
      if (!EMAIL.test(address)) return setError(t("invalidEmail"));
      setBusy(true);
      const { error: failed } = await supabase.auth.signInWithOtp({ email: address, options: { shouldCreateUser: true } });
      setBusy(false);
      if (failed) {
        // Name the known causes; only an unknown failure is generic (with its code, so it can be traced).
        const code = (failed as { code?: string }).code;
        if (failed.status === 429 || code === "over_email_send_rate_limit") return setError(t("tooMany"));
        if (code === "signup_disabled" || code === "otp_disabled") return setError(t("unknownEmail"));
        if (code === "email_address_not_authorized") return setError(t("emailNotAllowed"));
        return setError(t("genericWithCode", { code: code ?? String(failed.status ?? "network") }));
      }
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

  const verify = async (entered = code) => {
    if (!sentTo || busy) return;
    setBusy(true);
    setError(null);
    const { error: failed } = await supabase.auth.verifyOtp(
      channel === "email" ? { email: sentTo, token: entered.trim(), type: "email" } : { phone: sentTo, token: entered.trim(), type: "sms" },
    );
    setBusy(false);
    if (failed) return setError(t("invalidCode"));
    const { data: level } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();
    if (needsCodeStep(level?.currentLevel, level?.nextLevel)) {
      setStepTwo(true);
      setCode("");
      return;
    }
    finish();
  };

  return (
    <AuthShell>
      <FadeIn index={0} style={{ alignItems: "center", gap: 6 }}>
        <DepthLogo size={0.8} />
        <Heading palette={palette}>{needsCode ? tSecurity("challenge.title") : t("title")}</Heading>
        <Text style={[styles.muted, { color: palette.muted, textAlign: "center" }]}>{needsCode ? tSecurity("challenge.subtitle") : sentTo ? t(channel === "email" ? "codeSent" : "codeSentPhone", { target: ltr(sentTo) }) : t("subtitle")}</Text>
      </FadeIn>
      <AuthCard>
        {needsCode ? (
          <>
            <OtpInput
              value={code}
              onChange={setCode}
              length={CODE_LENGTH}
              palette={palette}
              label={tSecurity("mfa.code")}
              invalid={!!error}
              onComplete={(full) => void verifyAuthenticator(full)}
            />
            <ErrorText message={error} palette={palette} />
            <Button label={tSecurity("challenge.submit")} palette={palette} busy={busy} disabled={code.length < CODE_LENGTH} onPress={() => void verifyAuthenticator()} />
            <Button label={tSecurity("challenge.signOut")} variant="secondary" palette={palette} onPress={() => void supabase.auth.signOut().then(() => { setStepTwo(false); setSentTo(null); setCode(""); setError(null); })} />
          </>
        ) : sentTo ? (
          <>
            <OtpInput
              value={code}
              onChange={setCode}
              length={OTP_LENGTH}
              palette={palette}
              label={t(channel === "email" ? "code" : "codePhone")}
              invalid={!!error}
              onComplete={(full) => void verify(full)}
            />
            <ErrorText message={error} palette={palette} />
            <Button label={t("verify")} palette={palette} busy={busy} disabled={code.length < OTP_LENGTH} onPress={() => void verify()} />
            <Button label={tAuth("resend")} variant="secondary" palette={palette} disabled={busy} onPress={() => void sendCode()} />
            <Button label={t(channel === "email" ? "changeEmail" : "changePhone")} variant="secondary" palette={palette} onPress={() => { setSentTo(null); setCode(""); setError(null); }} />
          </>
        ) : (
          <>
            {channels.length > 1 && (
              <SegmentedControl
                label={tAuth("channelLabel")}
                value={channel}
                options={channels.map((option) => ({ value: option, label: t(`channel.${option}`) }))}
                onChange={(option) => {
                  setChannel(option);
                  setError(null);
                }}
              />
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
      </AuthCard>
      <Text style={[styles.muted, { color: palette.muted, textAlign: "center", fontSize: 13 }]}>{tAuth("tagline")}</Text>
    </AuthShell>
  );
}
