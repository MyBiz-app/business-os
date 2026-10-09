import type { components } from "@business-os/api-client";
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { Linking, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { BackBar, Badge } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Document = components["schemas"]["Document"];

/** My documents (#45): what the business shared with me; open them, sign the ones that ask. */
export default function Documents() {
  const t = useTranslations("documents");
  const tProfile = useTranslations("client.profile");
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();
  const [signing, setSigning] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!business) return [] as Document[];
    return unwrap(await api.GET("/client/documents", { params: scope }));
  }, [api, scope, business]);
  const { data, loading, reload } = useLoad(load);
  if (!business) return null;
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: business.time_zone });

  const open = async (document: Document) => {
    setError(null);
    try {
      const link = unwrap(
        await api.POST("/client/documents/{document_id}/link", { params: { ...scope, path: { document_id: document.id } } }),
      );
      await Linking.openURL(link.url);
    } catch {
      setError(t("signFailed"));
    }
  };

  const sign = async (document: Document) => {
    setError(null);
    try {
      unwrap(
        await api.POST("/client/documents/{document_id}/sign", {
          params: { ...scope, path: { document_id: document.id } },
          body: { name },
        }),
      );
      setSigning(null);
      setName("");
      await reload();
    } catch {
      setError(t("signFailed"));
    }
  };

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <BackBar label={tProfile("title")} palette={palette} onPress={() => router.back()} />
      <Heading palette={palette}>{t("mine")}</Heading>
      <Text style={[styles.muted, { color: palette.muted }]}>{t("mineHint")}</Text>
      <ErrorText message={error} palette={palette} />
      {data && data.length === 0 && (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("none")}</Text>
        </Card>
      )}
      {data?.map((document) => (
        <Card key={document.id} palette={palette}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <Text style={[styles.h2, { color: palette.foreground, flex: 1 }]}>{document.name}</Text>
            {document.sign_requested &&
              (document.signed_at ? (
                <Badge label={t("signedBy", { name: document.signed_name ?? "", date: date.format(new Date(document.signed_at)) })} tone="success" palette={palette} />
              ) : (
                <Badge label={t("waitingSignature")} tone="danger" palette={palette} />
              ))}
          </View>
          <Text style={[styles.muted, { color: palette.muted }]}>
            {t(`kinds.${document.kind}`)} · {date.format(new Date(document.created_at))}
          </Text>
          <Button label={t("open")} accessibilityLabel={`${t("open")} – ${document.name}`} variant="secondary" palette={palette} onPress={() => void open(document)} />
          {document.sign_requested && !document.signed_at && (
            signing === document.id ? (
              <View style={{ gap: 8 }}>
                <Field label={t("signName")} hint={t("signHint")} palette={palette} value={name} onChangeText={setName} autoComplete="name" />
                <Button label={t("sign")} palette={palette} disabled={!name.trim()} onPress={() => void sign(document)} />
              </View>
            ) : (
              <Button label={t("sign")} accessibilityLabel={`${t("sign")} – ${document.name}`} palette={palette} onPress={() => setSigning(document.id)} />
            )
          )}
        </Card>
      ))}
    </Screen>
  );
}
