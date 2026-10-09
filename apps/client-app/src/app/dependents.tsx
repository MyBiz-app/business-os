import type { components } from "@business-os/api-client";
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { Text, View } from "react-native";
import { useTranslations } from "use-intl";

import { DependentForm, type DependentBody } from "@business-os/app-kit/components/dependent-form";
import { BackBar, Badge, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Dependent = components["schemas"]["Dependent"];

/** My pets / my children: who the client books for (industries that keep them). */
export default function Dependents() {
  const t = useTranslations("dependents");
  const tProfile = useTranslations("client.profile");
  const { api, scope, business, palette } = useBusiness();
  const [editing, setEditing] = useState<string | null>(null);
  const kind = business?.dependents;

  const load = useCallback(async () => {
    if (!business?.dependents) return null;
    const [settings, dependents] = await Promise.all([
      api.GET("/client/dependents/settings", { params: scope }).then(unwrap),
      api.GET("/client/dependents", { params: scope }).then(unwrap),
    ]);
    return { settings, dependents };
  }, [api, scope, business]);
  const { data, reload } = useLoad(load);
  if (!business || !kind) return null;

  const add = async (body: DependentBody) => {
    unwrap(await api.POST("/client/dependents", { params: scope, body }));
    await reload();
  };
  const save = (dependent: Dependent) => async (body: DependentBody) => {
    unwrap(await api.PATCH("/client/dependents/{dependent_id}", { params: { ...scope, path: { dependent_id: dependent.id } }, body }));
    setEditing(null);
    await reload();
  };
  const setActive = async (dependent: Dependent, active: boolean) => {
    unwrap(
      await api.PATCH("/client/dependents/{dependent_id}", {
        params: { ...scope, path: { dependent_id: dependent.id } },
        body: { active },
      }),
    );
    await reload();
  };

  return (
    <Screen palette={palette}>
      <BackBar label={tProfile("title")} palette={palette} onPress={() => router.back()} />
      <Heading palette={palette}>{t(`mine.${kind}`)}</Heading>
      {data && data.dependents.length === 0 && (
        <Text style={[styles.muted, { color: palette.muted }]}>{t(`mineHint.${kind}`)}</Text>
      )}
      {data?.dependents.map((dependent) => (
        <Card key={dependent.id} palette={palette}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <Text style={[styles.h2, { color: palette.foreground, flex: 1 }]}>{dependent.name}</Text>
            {!dependent.active && <Badge label={t("inactive")} palette={palette} />}
          </View>
          {dependent.notes ? <Text style={[styles.muted, { color: palette.muted }]}>{dependent.notes}</Text> : null}
          {editing === dependent.id ? (
            <DependentForm
              kind={kind}
              fields={data.settings.fields}
              dependent={dependent}
              palette={palette}
              onSave={save(dependent)}
            />
          ) : (
            <View style={{ gap: 8 }}>
              <Button
                label={t("edit", { name: dependent.name })}
                variant="secondary"
                palette={palette}
                onPress={() => setEditing(dependent.id)}
              />
              <Button
                label={dependent.active ? t("retire") : t("restore")}
                variant="secondary"
                palette={palette}
                onPress={() => void setActive(dependent, !dependent.active)}
              />
            </View>
          )}
        </Card>
      ))}
      {data && (
        <Card palette={palette}>
          <SectionTitle title={t(`add.${kind}`)} palette={palette} />
          <DependentForm kind={kind} fields={data.settings.fields} palette={palette} onSave={add} />
        </Card>
      )}
    </Screen>
  );
}
