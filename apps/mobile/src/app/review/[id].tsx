import Ionicons from "@expo/vector-icons/Ionicons";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslations } from "use-intl";

import { Button, Card, ErrorText, Field, Heading, Screen, styles } from "@/components/ui";
import { useBusiness } from "@/providers/business-provider";

const ERRORS = ["already_reviewed", "not_reviewable"] as const;

/** Rate a visit: 1–5 stars and an optional comment. */
export default function Review() {
  const t = useTranslations("client.review");
  const { id, service } = useLocalSearchParams<{ id: string; service?: string }>();
  const { api, scope, business, palette } = useBusiness();
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!business || !id) return null;

  const send = async () => {
    setBusy(true);
    setError(null);
    const result = await api
      .POST("/client/bookings/{booking_id}/review", {
        params: { ...scope, path: { booking_id: id } },
        body: { rating, comment: comment || null },
      })
      .catch(() => null);
    setBusy(false);
    if (result?.data) return setDone(true);
    const detail = (result?.error as { detail?: string } | undefined)?.detail;
    setError(ERRORS.includes(detail as (typeof ERRORS)[number]) ? t(`errors.${detail as (typeof ERRORS)[number]}`) : t("errors.generic"));
  };
  const leave = () => (router.canGoBack() ? router.back() : router.replace("/home"));

  return (
    <Screen palette={palette}>
      <Heading palette={palette}>{service ? t("cardTitle", { service }) : t("title")}</Heading>
      <Card palette={palette}>
        {done ? (
          <View style={local.done}>
            <Ionicons name="heart" size={48} color={palette.primary} />
            <Text accessibilityRole="alert" style={[local.thanks, { color: palette.foreground }]}>
              {t("thanks")}
            </Text>
          </View>
        ) : (
          <>
            <Text style={[styles.muted, { color: palette.foreground }]}>{t("question")}</Text>
            <View role="radiogroup" aria-label={t("question")} style={local.stars}>
              {[1, 2, 3, 4, 5].map((n) => (
                <Pressable
                  key={n}
                  role="radio"
                  aria-checked={rating === n}
                  accessibilityLabel={t("star", { count: n })}
                  onPress={() => setRating(n)}
                  hitSlop={6}
                  style={local.star}
                >
                  <Ionicons name={n <= rating ? "star" : "star-outline"} size={40} color={n <= rating ? "#f59e0b" : palette.muted} />
                </Pressable>
              ))}
            </View>
            <Field label={t("comment")} palette={palette} value={comment} onChangeText={setComment} maxLength={1000} multiline />
            <ErrorText message={error} palette={palette} />
            <Button label={t("send")} palette={palette} busy={busy} disabled={rating === 0} onPress={() => void send()} />
          </>
        )}
      </Card>
      <Button label={t("back")} variant="secondary" palette={palette} onPress={leave} />
    </Screen>
  );
}

const local = StyleSheet.create({
  stars: { flexDirection: "row", justifyContent: "center", gap: 6, marginVertical: 8 },
  star: { padding: 2 },
  done: { alignItems: "center", gap: 10, paddingVertical: 16 },
  thanks: { fontSize: 18, fontWeight: "700", textAlign: "center" },
});
