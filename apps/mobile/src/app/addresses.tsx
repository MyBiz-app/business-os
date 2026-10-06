import type { components } from "@business-os/api-client";
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { Text } from "react-native";
import { useTranslations } from "use-intl";

import { BackBar, Badge, ListRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Address = components["schemas"]["Address"];

const line = (a: Address) => [a.street, a.details, a.city].filter(Boolean).join(", ");

/** My addresses: where on-site jobs happen (#42). */
export default function Addresses() {
  const t = useTranslations("jobs");
  const tAddress = useTranslations("jobs.address");
  const tProfile = useTranslations("client.profile");
  const { api, scope, business, palette } = useBusiness();
  const [street, setStreet] = useState("");
  const [city, setCity] = useState("");
  const [details, setDetails] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!business) return [] as Address[];
    return unwrap(await api.GET("/client/addresses", { params: scope }));
  }, [api, scope, business]);
  const { data, reload } = useLoad(load);
  if (!business) return null;

  const add = async () => {
    if (!street.trim() || !city.trim()) return setError(tAddress("required"));
    setBusy(true);
    setError(null);
    try {
      unwrap(
        await api.POST("/client/addresses", {
          params: scope,
          body: { street, city, details: details || null, notes: notes || null },
        }),
      );
      setStreet("");
      setCity("");
      setDetails("");
      setNotes("");
      await reload();
    } catch {
      setError(tAddress("saveFailed"));
    } finally {
      setBusy(false);
    }
  };

  const retire = async (address: Address) => {
    unwrap(
      await api.PATCH("/client/addresses/{address_id}", {
        params: { ...scope, path: { address_id: address.id } },
        body: { active: !address.active },
      }),
    );
    await reload();
  };

  return (
    <Screen palette={palette}>
      <BackBar label={tProfile("title")} palette={palette} onPress={() => router.back()} />
      <Heading palette={palette}>{t("myAddresses")}</Heading>
      <Text style={[styles.muted, { color: palette.muted }]}>{t("myAddressesHint")}</Text>
      {data?.map((address) => (
        <ListRow
          key={address.id}
          palette={palette}
          title={line(address)}
          subtitle={address.notes ?? undefined}
          accessibilityLabel={`${address.active ? tAddress("retire") : tAddress("restore")} – ${line(address)}`}
          onPress={() => void retire(address)}
          trailing={<Badge label={address.active ? tAddress("retire") : tAddress("inactive")} palette={palette} />}
        />
      ))}
      <Card palette={palette}>
        <SectionTitle title={tAddress("add")} palette={palette} />
        <Field label={tAddress("street")} palette={palette} value={street} onChangeText={setStreet} autoComplete="street-address" maxLength={200} />
        <Field label={tAddress("city")} palette={palette} value={city} onChangeText={setCity} maxLength={80} />
        <Field label={tAddress("details")} palette={palette} value={details} onChangeText={setDetails} maxLength={200} />
        <Field label={tAddress("notes")} hint={tAddress("notesHint")} palette={palette} value={notes} onChangeText={setNotes} maxLength={500} />
        <ErrorText message={error} palette={palette} />
        <Button label={tAddress("add")} palette={palette} busy={busy} onPress={() => void add()} />
      </Card>
    </Screen>
  );
}
