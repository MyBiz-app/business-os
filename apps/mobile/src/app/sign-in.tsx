import { router } from "expo-router";
import { useState } from "react";
import { Text } from "react-native";
import { useTranslations } from "use-intl";

import { Button, ErrorText, Field, Heading, Screen, styles } from "@/components/ui";
import { supabase } from "@/lib/supabase";
import { useTheme } from "@/providers/theme-provider";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Passwordless sign-in: the user gets a 6-digit code by email (new users are signed up). */
export default function SignIn() {
  const t = useTranslations("client.signIn");
  const { palette } = useTheme();
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
    router.replace("/");
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
            onChangeText={(value) => setCode(value.replace(/\D/g, "").slice(0, 6))}
            keyboardType="number-pad"
            autoComplete="one-time-code"
            textContentType="oneTimeCode"
            autoFocus
            onSubmitEditing={() => void verify()}
          />
          <ErrorText message={error} palette={palette} />
          <Button label={t("verify")} palette={palette} busy={busy} disabled={code.length < 6} onPress={() => void verify()} />
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
