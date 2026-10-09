import { useState } from "react";
import { Text } from "react-native";
import { useTranslations } from "use-intl";

import { Button, Card, ErrorText, Field, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useBusiness } from "@/providers/business-provider";

/** The client's own name and phone in the current business. */
export function ProfileForm() {
  const t = useTranslations("client.profile");
  const { api, scope, business, palette, refresh } = useBusiness();
  const [firstName, setFirstName] = useState(business?.first_name ?? "");
  const [lastName, setLastName] = useState(business?.last_name ?? "");
  const [phone, setPhone] = useState(business?.phone ?? "");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<{ ok: boolean; message: string } | null>(null);
  if (!business) return null;

  const save = async () => {
    if (!firstName.trim()) return setStatus({ ok: false, message: t("firstNameRequired") });
    setBusy(true);
    setStatus(null);
    try {
      unwrap(
        await api.PATCH("/client/profile", {
          params: scope,
          body: { first_name: firstName, last_name: lastName || null, phone: phone || null },
        }),
      );
      await refresh();
      setStatus({ ok: true, message: t("saved") });
    } catch {
      setStatus({ ok: false, message: t("saveFailed") });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card palette={palette}>
      <Text style={[styles.h2, { color: palette.foreground }]}>{t("details")}</Text>
      <Field label={t("firstName")} palette={palette} value={firstName} onChangeText={setFirstName} autoComplete="given-name" />
      <Field label={t("lastName")} palette={palette} value={lastName} onChangeText={setLastName} autoComplete="family-name" />
      <Field
        label={t("phone")}
        palette={palette}
        value={phone}
        onChangeText={setPhone}
        keyboardType="phone-pad"
        autoComplete="tel"
        textContentType="telephoneNumber"
      />
      {status?.ok ? (
        <Text accessibilityLiveRegion="polite" style={[styles.muted, { color: palette.primary }]}>
          {status.message}
        </Text>
      ) : (
        <ErrorText message={status?.message} palette={palette} />
      )}
      <Button label={t("save")} palette={palette} busy={busy} onPress={() => void save()} />
    </Card>
  );
}
