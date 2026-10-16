import { useEffect, useState } from "react";
import { Image, Linking, Modal, StyleSheet, View } from "react-native";
import { useTranslations } from "use-intl";

import { apiClient } from "../lib/api";
import { tint } from "../lib/brand";
import { useSession } from "../providers/session-provider";
import { useTheme } from "../providers/theme-provider";
import { Text } from "./text";
import { Button, Heading, styles } from "./ui";

type Item = { id: string; subject: string; body: string; ctaLabel: string; ctaUrl: string; imageUrl: string };

/** The pop-ups MyBiz sent to this person: one at a time, shown when they open the app, until
 * they close it (then it never comes back). A failure to load them never blocks the app. */
export function AnnouncementsModal() {
  const t = useTranslations("app.announcements");
  const { palette } = useTheme();
  const { session } = useSession();
  const userId = session?.user.id;
  const [queue, setQueue] = useState<Item[]>([]);
  const current = queue[0];

  useEffect(() => {
    if (!userId) {
      setQueue([]);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const { data } = await apiClient().GET("/me/announcements");
        if (cancelled || !data) return;
        setQueue(
          data.map((a) => ({
            id: a.id,
            subject: a.texts.subject ?? "",
            body: a.texts.body ?? "",
            ctaLabel: a.texts.cta_label ?? "",
            ctaUrl: a.texts.cta_url ?? "",
            imageUrl: a.texts.image_url ?? "",
          })),
        );
      } catch {
        // announcements are a convenience
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const currentId = current?.id;
  useEffect(() => {
    if (!currentId) return;
    void apiClient()
      .POST("/me/announcements/{announcement_id}/{event}", { params: { path: { announcement_id: currentId, event: "viewed" } } })
      .catch(() => undefined);
  }, [currentId]);

  if (!current) return null;
  const mark = (event: "dismissed" | "clicked") =>
    void apiClient()
      .POST("/me/announcements/{announcement_id}/{event}", { params: { path: { announcement_id: current.id, event } } })
      .catch(() => undefined);
  const dismiss = () => {
    mark("dismissed");
    setQueue((q) => q.slice(1));
  };

  return (
    <Modal visible transparent animationType="fade" onRequestClose={dismiss} accessibilityLabel={t("label", { brand: "MyBiz" })}>
      <View style={styles2.scrim}>
        <View style={[styles2.sheet, { backgroundColor: palette.surface, borderColor: palette.border }]}>
          {current.imageUrl ? <Image source={{ uri: current.imageUrl }} style={styles2.image} accessibilityIgnoresInvertColors /> : null}
          <Heading palette={palette} level={2}>
            {current.subject}
          </Heading>
          <Text style={[styles.muted, { color: palette.foreground }]}>{current.body}</Text>
          {current.ctaUrl ? (
            <Button
              label={current.ctaLabel || t("close")}
              palette={palette}
              onPress={() => {
                mark("clicked");
                void Linking.openURL(current.ctaUrl).catch(() => undefined);
                setQueue((q) => q.slice(1));
              }}
            />
          ) : null}
          <Button label={t("close")} variant="secondary" palette={palette} onPress={dismiss} />
        </View>
      </View>
    </Modal>
  );
}

const styles2 = StyleSheet.create({
  scrim: { flex: 1, backgroundColor: tint("#000000", 0.5), alignItems: "center", justifyContent: "center", padding: 20 },
  sheet: { width: "100%", maxWidth: 420, borderRadius: 20, borderWidth: 1, padding: 20, gap: 12 },
  image: { width: "100%", height: 160, borderRadius: 12 },
});
