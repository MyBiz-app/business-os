import type { components } from "@business-os/api-client";
import { router } from "expo-router";
import { useState } from "react";
import { Text, View } from "react-native";
import { useTranslations } from "use-intl";

import { BackBar, PillRow } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Field, Heading, Screen } from "@business-os/app-kit/components/ui";
import { ApiError, unwrap } from "@business-os/app-kit/lib/api";
import { termsFor } from "@business-os/app-kit/lib/vertical";
import { useBusiness } from "@/providers/business-provider";

type Source = NonNullable<components["schemas"]["ClientCreate"]["source"]>;
const SOURCES: Source[] = ["walk_in", "referral", "instagram", "facebook", "google", "website", "other"];

/** Adding a client at the front desk: name, how to reach them and how they found the business.
 * They are filed under the current branch, as on the web. */
export default function NewClient() {
  const t = useTranslations("business.clients");
  const tClients = useTranslations("clients");
  const tTerms = useTranslations("terms");
  const { api, scope, tenant, palette } = useBusiness();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [source, setSource] = useState<Source>("walk_in");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!tenant) return null;
  const terms = termsFor(tenant);

  const save = async () => {
    if (!firstName.trim()) {
      setError(t("nameRequired"));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const client = unwrap(
        await api.POST("/clients", {
          params: scope,
          body: {
            first_name: firstName.trim(),
            last_name: lastName.trim() || null,
            phone: phone.trim() || null,
            email: email.trim() || null,
            source,
            status: "active",
          },
        }),
      );
      router.replace(`/client/${client.id}?created=1`);
    } catch (caught) {
      const code = caught instanceof ApiError ? caught.detail : undefined;
      setError(code === "email_taken" ? tClients("errors.email_taken") : tClients("errors.invalid"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Screen palette={palette}>
      <BackBar label={tTerms(`${terms}.clients`)} palette={palette} onPress={() => router.back()} />
      <Heading palette={palette}>{tTerms(`${terms}.newClient`)}</Heading>
      <Card palette={palette}>
        <Field label={tClients("firstName")} palette={palette} value={firstName} onChangeText={setFirstName} autoComplete="given-name" />
        <Field label={tClients("lastName")} palette={palette} value={lastName} onChangeText={setLastName} autoComplete="family-name" />
        <Field
          label={tClients("phone")}
          palette={palette}
          value={phone}
          onChangeText={setPhone}
          keyboardType="phone-pad"
          autoComplete="tel"
          style={{ writingDirection: "ltr" }}
        />
        <Field
          label={tClients("email")}
          palette={palette}
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          autoComplete="email"
          style={{ writingDirection: "ltr" }}
        />
        <View style={{ gap: 6 }}>
          <Text style={{ color: palette.foreground, fontSize: 14, fontWeight: "600", textAlign: "left" }}>{tClients("source")}</Text>
          <PillRow<Source>
            label={tClients("source")}
            palette={palette}
            value={source}
            onChange={setSource}
            options={SOURCES.map((value) => ({ value, label: tClients(`sources.${value}`) }))}
          />
        </View>
        <ErrorText message={error} palette={palette} />
        <Button label={tClients("create")} palette={palette} busy={saving} onPress={() => void save()} />
      </Card>
    </Screen>
  );
}
