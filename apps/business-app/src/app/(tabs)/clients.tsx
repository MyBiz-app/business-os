import { router } from "expo-router";
import { useCallback, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { useTranslations } from "use-intl";

import { Card, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { termsFor } from "@business-os/app-kit/lib/vertical";
import { useBusiness } from "@/providers/business-provider";

/** The business's clients, searchable, with a tap into each one. */
export default function Clients() {
  const t = useTranslations("business.clients");
  const tTerms = useTranslations("terms");
  const { api, scope, tenant, palette } = useBusiness();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");

  const load = useCallback(async () => {
    if (!tenant) return { items: [], total: 0 };
    return unwrap(
      await api.GET("/clients", { params: { ...scope, query: { search: query || undefined, limit: 50 } } }),
    );
  }, [api, scope, tenant, query]);
  const { data, loading, reload } = useLoad(load);
  if (!tenant) return null;
  const terms = termsFor(tenant);

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <Heading palette={palette}>{tTerms(`${terms}.clients`)}</Heading>
      <Field
        label={t("search")}
        palette={palette}
        value={search}
        onChangeText={setSearch}
        onSubmitEditing={() => setQuery(search.trim())}
        returnKeyType="search"
        autoCapitalize="none"
      />
      {(data?.items ?? []).length === 0 ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("none")}</Text>
        </Card>
      ) : (
        (data?.items ?? []).map((client) => (
          <Pressable
            key={client.id}
            accessibilityRole="button"
            onPress={() => router.push(`/client/${client.id}`)}
            style={({ pressed }) => [{ opacity: pressed ? 0.75 : 1 }]}
          >
            <Card palette={palette}>
              <View style={{ gap: 2 }}>
                <Text style={{ color: palette.foreground, fontWeight: "600" }}>
                  {[client.first_name, client.last_name].filter(Boolean).join(" ")}
                </Text>
                {client.phone && (
                  <Text style={{ color: palette.muted, fontSize: 13, writingDirection: "ltr" }}>
                    {client.phone}
                  </Text>
                )}
              </View>
            </Card>
          </Pressable>
        ))
      )}
    </Screen>
  );
}
