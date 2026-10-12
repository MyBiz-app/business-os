import { Redirect, router } from "expo-router";
import { useCallback, useState } from "react";
import { Text } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Button, Card, ErrorText, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { supabase } from "@business-os/app-kit/lib/supabase";
import { useBusiness } from "@/providers/business-provider";

/** A business that was closed: its owner can reopen it for 90 days; anyone else asks the owner. */
export default function Closed() {
  const t = useTranslations("closure");
  const locale = useLocale();
  const { api, palette, closedBusiness, refresh } = useBusiness();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const closure = useLoad(
    useCallback(async () => {
      if (!closedBusiness?.owner) return null;
      return unwrap(await api.GET("/tenants/current/closure", { params: { header: { "X-Tenant-Id": closedBusiness.id } } }));
    }, [api, closedBusiness]),
  );

  if (!closedBusiness) return <Redirect href="/" />;
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "long" });

  const reopen = async () => {
    setBusy(true);
    setFailed(false);
    try {
      unwrap(await api.DELETE("/tenants/current/closure", { params: { header: { "X-Tenant-Id": closedBusiness.id } } }));
      await refresh();
      router.replace("/");
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  const data = closure.data;
  return (
    <Screen palette={palette}>
      <Heading palette={palette}>{t("closedTitle")}</Heading>
      <Card palette={palette}>
        {closedBusiness.owner && data?.closed_at && data.delete_after ? (
          <>
            <Text style={[styles.muted, { color: palette.muted }]}>{t("closedOn", { date: date.format(new Date(data.closed_at)) })}</Text>
            <Text style={{ color: palette.foreground }}>{t("deleteOn", { date: date.format(new Date(data.delete_after)) })}</Text>
          </>
        ) : (
          !closedBusiness.owner && <Text style={[styles.muted, { color: palette.muted }]}>{t("notOwner", { name: closedBusiness.name })}</Text>
        )}
      </Card>
      <ErrorText message={failed ? t("errors.generic") : null} palette={palette} />
      {closedBusiness.owner && <Button label={t("reopen")} palette={palette} busy={busy} onPress={() => void reopen()} />}
      <Button
        label={t("signOut")}
        variant="secondary"
        palette={palette}
        onPress={() => {
          void supabase.auth.signOut().then(() => router.replace("/sign-in"));
        }}
      />
    </Screen>
  );
}
