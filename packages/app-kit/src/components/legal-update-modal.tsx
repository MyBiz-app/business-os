import { useCallback, useEffect, useState } from "react";
import { Linking, Modal, StyleSheet, View } from "react-native";
import { useTranslations } from "use-intl";

import { apiClient } from "../lib/api";
import { WEB_URL } from "../lib/env";
import { useSession } from "../providers/session-provider";
import { useTheme } from "../providers/theme-provider";
import { radius, scrimColor } from "../lib/theme";
import { Text } from "./text";
import { Button, ErrorText, Heading, styles } from "./ui";

type Pending = { document: string; version: string };

/** Asks the person to accept the legal documents they have not accepted in their current
 * version (ones that changed since they accepted). Shown when the app opens, until they accept; a
 * failure to load never blocks the app. Someone brand new, with no business and no joined business
 * yet, is not asked: they accept once, when they join or create a business. */
export function LegalUpdateModal() {
  const t = useTranslations("legalUpdate");
  const { palette, scheme } = useTheme();
  const { session } = useSession();
  const userId = session?.user.id;
  const [pending, setPending] = useState<Pending[]>([]);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!userId) {
      setPending([]);
      return;
    }
    let cancelled = false;
    void apiClient()
      .GET("/me/legal")
      .then(async ({ data }) => {
        if (cancelled || !data?.length) return;
        const [me, joined] = await Promise.all([apiClient().GET("/me"), apiClient().GET("/client/businesses")]);
        const isNew = !me.data?.memberships.length && !joined.data?.length;
        if (!cancelled && !isNew) setPending(data);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const accept = useCallback(async () => {
    setBusy(true);
    setFailed(false);
    try {
      const { data } = await apiClient().POST("/me/legal", {
        body: { documents: Object.fromEntries(pending.map((item) => [item.document, item.version])) },
      });
      if (!data) throw new Error("not saved");
      setPending(data);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }, [pending]);

  if (pending.length === 0) return null;
  return (
    <Modal visible transparent animationType="fade" accessibilityLabel={t("title")}>
      <View style={[local.scrim, { backgroundColor: scrimColor(scheme) }]}>
        <View style={[local.sheet, { backgroundColor: palette.surface, borderColor: palette.border }]}>
          <Heading palette={palette} level={2}>
            {t("title")}
          </Heading>
          <Text style={[styles.muted, { color: palette.foreground }]}>{t("text")}</Text>
          {pending.map((item) => (
            <Button
              key={item.document}
              label={t(`documents.${item.document as "terms" | "privacy" | "dpa"}`)}
              variant="secondary"
              palette={palette}
              onPress={() => void Linking.openURL(`${WEB_URL}/legal/${item.document}`).catch(() => undefined)}
            />
          ))}
          <ErrorText message={failed ? t("failed") : null} palette={palette} />
          <Button label={t("accept")} palette={palette} busy={busy} onPress={() => void accept()} />
        </View>
      </View>
    </Modal>
  );
}

const local = StyleSheet.create({
  scrim: { flex: 1, alignItems: "center", justifyContent: "center", padding: 20 },
  sheet: { width: "100%", maxWidth: 420, borderRadius: radius.card, borderWidth: 1, padding: 20, gap: 12 },
});
