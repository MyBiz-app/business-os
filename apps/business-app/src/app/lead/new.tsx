import type { components } from "@business-os/api-client";
import { router } from "expo-router";
import { useState } from "react";
import { Text, View } from "react-native";
import { useTranslations } from "use-intl";

import { BackBar, PillRow } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Field, Heading, Screen } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useBusiness } from "@/providers/business-provider";

type Source = NonNullable<components["schemas"]["LeadCreate"]["source"]>;
const SOURCES: Source[] = ["walk_in", "referral", "instagram", "facebook", "google", "website", "manual", "other"];

/** A new lead, written down while they are on the phone or at the door. */
export default function NewLead() {
  const tBusiness = useTranslations("business");
  const tLeads = useTranslations("leads");
  const { api, scope, tenant, palette } = useBusiness();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [interest, setInterest] = useState("");
  const [source, setSource] = useState<Source>("walk_in");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!tenant) return null;

  const save = async () => {
    if (!firstName.trim()) {
      setError(tBusiness("clients.nameRequired"));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const lead = unwrap(
        await api.POST("/leads", {
          params: scope,
          body: {
            first_name: firstName.trim(),
            last_name: lastName.trim() || null,
            phone: phone.trim() || null,
            email: email.trim() || null,
            interest: interest.trim() || null,
            source,
          },
        }),
      );
      router.replace(`/lead/${lead.id}?created=1`);
    } catch {
      setError(tBusiness("error"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Screen palette={palette}>
      <BackBar label={tLeads("title")} palette={palette} onPress={() => router.back()} />
      <Heading palette={palette}>{tLeads("new")}</Heading>
      <Card palette={palette}>
        <Field label={tLeads("firstName")} palette={palette} value={firstName} onChangeText={setFirstName} autoComplete="given-name" />
        <Field label={tLeads("lastName")} palette={palette} value={lastName} onChangeText={setLastName} autoComplete="family-name" />
        <Field
          label={tLeads("phone")}
          palette={palette}
          value={phone}
          onChangeText={setPhone}
          keyboardType="phone-pad"
          autoComplete="tel"
          style={{ writingDirection: "ltr" }}
        />
        <Field
          label={tLeads("email")}
          palette={palette}
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          autoComplete="email"
          style={{ writingDirection: "ltr" }}
        />
        <Field label={tLeads("interest")} palette={palette} value={interest} onChangeText={setInterest} />
        <View style={{ gap: 6 }}>
          <Text style={{ color: palette.foreground, fontSize: 14, fontWeight: "600", textAlign: "left" }}>{tLeads("source")}</Text>
          <PillRow<Source>
            label={tLeads("source")}
            palette={palette}
            value={source}
            onChange={setSource}
            options={SOURCES.map((value) => ({ value, label: tLeads(`sources.${value}`) }))}
          />
        </View>
        <ErrorText message={error} palette={palette} />
        <Button label={tLeads("create")} palette={palette} busy={saving} onPress={() => void save()} />
      </Card>
    </Screen>
  );
}
