import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Text } from "../components/text";
import { useTranslations } from "use-intl";

import { Button, ErrorText, Field, Heading, Screen, styles } from "../components/ui";
import { supabase } from "../lib/supabase";
import { useTheme } from "../providers/theme-provider";

// The email OTP length is a Supabase project setting (6 locally, 8 on hosted projects).
const MIN_CODE_LENGTH = 6;
const MAX_CODE_LENGTH = 10;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Passwordless sign-in, shared by the three apps: the user gets a numeric code by email (Supabase decides the length, so the input accepts 6 to 10 digits) (new
 * users are signed up). Each app's `sign-in` route re-exports it. */
export function SignInScreen() {
  const t = useTranslations("client.signIn");
  const { palette } = useTheme();
  // Set when a join link sent the user here first.
  const { code: joinCode } = useLocalSearchParams<{ code?: string }>();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendCode = async () => {
    const address = email.trim().toLowerCase();
    if (!EMAIL.test(address)) return setError(t("invalidEmail"));
    setBusy(true);
    setError(null);
    const { error: failed } = await supabase.auth.signInWithOtp({ email: address, options: { shouldCreateUser: true } });
    setBusy(false);
    if (failed) return setError(failed.status === 429 ? t("tooMany") : t("generic"));
    setSentTo(address);
    setCode("");
  };

  const verify = async () => {
    if (!sentTo) return;
    setBusy(true);
    setError(null);
    const { error: failed } = await supabase.auth.verifyOtp({ email: sentTo, token: code.trim(), type: "email" });
    setBusy(false);
    if (failed) return setError(t("invalidCode"));
    router.replace(joinCode ? { pathname: "/join", params: { code: joinCode } } : "/");
  };

  return (
    <Screen palette={palette}>
      <Heading palette={palette}>{t("title")}</Heading>
      {sentTo ? (
        <>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("codeSent", { email: sentTo })}</Text>
          <Field
            label={t("code")}
            palette={palette}
            value={code}
            onChangeText={(value) => setCode(value.replace(/\D/g, "").slice(0, MAX_CODE_LENGTH))}
            keyboardType="number-pad"
            autoComplete="one-time-code"
            textContentType="oneTimeCode"
            autoFocus
            onSubmitEditing={() => void verify()}
          />
          <ErrorText message={error} palette={palette} />
          <Button label={t("verify")} palette={palette} busy={busy} disabled={code.length < MIN_CODE_LENGTH} onPress={() => void verify()} />
          <Button label={t("changeEmail")} variant="secondary" palette={palette} onPress={() => setSentTo(null)} />
        </>
      ) : (
        <>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("subtitle")}</Text>
          <Field
            label={t("email")}
            palette={palette}
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            autoComplete="email"
            textContentType="emailAddress"
            onSubmitEditing={() => void sendCode()}
          />
          <ErrorText message={error} palette={palette} />
          <Button label={t("sendCode")} palette={palette} busy={busy} onPress={() => void sendCode()} />
        </>
      )}
    </Screen>
  );
}
