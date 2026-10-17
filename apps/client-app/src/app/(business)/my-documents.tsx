import type { components } from "@business-os/api-client";
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { Linking } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { BackBar } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Heading, LoadError, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useStaff } from "@/providers/staff-provider";

type FileRow = components["schemas"]["FileOut"];

/** "My documents": the payslips and papers the business filed for this person. */
export default function MyDocuments() {
  const t = useTranslations("business.myDocuments");
  const tMe = useTranslations("business.me");
  const locale = useLocale();
  const { api, scope, tenant, palette } = useStaff();
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!tenant) return [] as FileRow[];
    return unwrap(await api.GET("/files/mine", { params: scope }));
  }, [api, scope, tenant]);
  const { data, error: loadError, loading, reload } = useLoad(load);
  if (!tenant) return null;
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: tenant.time_zone });

  const open = async (file: FileRow) => {
    setError(null);
    try {
      const link = unwrap(await api.POST("/files/{file_id}/link", { params: { ...scope, path: { file_id: file.id } } }));
      await Linking.openURL(link.url);
    } catch {
      setError(t("failed"));
    }
  };

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <BackBar label={tMe("title")} palette={palette} onPress={() => router.back()} />
      <Heading palette={palette}>{t("title")}</Heading>
      {loadError !== undefined && !data && <LoadError palette={palette} onRetry={() => void reload()} />}
      <Text style={[styles.muted, { color: palette.muted }]}>{t("hint")}</Text>
      <ErrorText message={error} palette={palette} />
      {data && data.length === 0 && (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("none")}</Text>
        </Card>
      )}
      {data?.map((file) => (
        <Card key={file.id} palette={palette}>
          <Text style={[styles.h2, { color: palette.foreground }]}>{file.name}</Text>
          <Text style={[styles.muted, { color: palette.muted }]}>{date.format(new Date(file.created_at))}</Text>
          <Button label={t("openFile")} accessibilityLabel={`${t("openFile")} - ${file.name}`} variant="secondary" palette={palette} onPress={() => void open(file)} />
        </Card>
      ))}
    </Screen>
  );
}
