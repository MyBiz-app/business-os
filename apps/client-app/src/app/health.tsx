import type { components } from "@business-os/api-client";
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { SegmentedControl } from "@business-os/app-kit/components/segmented-control";
import { Button, Card, ErrorText, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type MyHealth = components["schemas"]["MyHealth"];
type Answer = "yes" | "no";

/** The business's health declaration: yes/no questions, the statement, and a typed signature. */
export default function Health() {
  const t = useTranslations("client.health");
  const tHealth = useTranslations("health");
  const locale = useLocale() === "en" ? "en" : "he";
  const { api, scope, business, palette } = useBusiness();

  const load = useCallback(async () => {
    if (!business) return undefined;
    return unwrap(await api.GET("/client/health-declaration", { params: { ...scope, query: { locale } } }));
  }, [api, scope, business, locale]);
  const { data, loading, reload } = useLoad(load);
  const [saved, setSaved] = useState<MyHealth | null>(null);
  const [editing, setEditing] = useState(false);
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const [name, setName] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const health = saved ?? data;
  if (!business) return null;
  const form = health?.form;
  const current = health?.current;
  const showForm = !!form && (editing || !current || health.state === "expired");
  const dateFormat = new Intl.DateTimeFormat(locale, { dateStyle: "long", timeZone: "UTC" });

  const submit = async () => {
    if (!form) return;
    if (form.questions.some((q) => !answers[q.id])) return setError(t("answerAll"));
    if (name.trim().length < 2) return setError(t("nameRequired"));
    if (!accepted) return setError(t("acceptRequired"));
    setBusy(true);
    setError(null);
    try {
      const result = unwrap(
        await api.POST("/client/health-declaration", {
          params: scope,
          body: {
            locale,
            answers: Object.fromEntries(form.questions.map((q) => [q.id, answers[q.id] === "yes"])),
            signed_name: name.trim(),
            accept: true,
          },
        }),
      );
      setSaved(result);
      setEditing(false);
    } catch {
      setError(t("generic"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload().then(() => setSaved(null))}>
      <Heading palette={palette}>{t("title")}</Heading>

      {!loading && !form && <Text style={[styles.muted, { color: palette.muted }]}>{t("noForm")}</Text>}

      {current && !showForm && health && (
        <Card palette={palette}>
          <Text accessibilityLiveRegion="polite" style={[styles.h2, { color: palette.foreground }]}>
            {tHealth(`states.${health.state}`)}
          </Text>
          <Text style={[styles.muted, { color: palette.muted }]}>
            {health.state === "needs_review"
              ? t("reviewPending")
              : health.state === "rejected"
                ? t("rejected")
                : health.state === "expiring"
                  ? t("expiringSoon", { date: dateFormat.format(new Date(`${current.valid_until}T12:00:00Z`)) })
                  : t("validUntil", { date: dateFormat.format(new Date(`${current.valid_until}T12:00:00Z`)) })}
          </Text>
          {current.review_note && (
            <Text style={[styles.muted, { color: palette.foreground }]}>{tHealth("reviewNote", { note: current.review_note })}</Text>
          )}
          <Button label={t("update")} variant="secondary" palette={palette} onPress={() => setEditing(true)} />
        </Card>
      )}

      {showForm && form && (
        <>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("intro")}</Text>
          {form.questions.map((question, index) => (
            <Card key={question.id} palette={palette}>
              <SegmentedControl
                label={`${index + 1}. ${question.text}`}
                options={[
                  { value: "no", label: tHealth("no") },
                  { value: "yes", label: tHealth("yes") },
                ]}
                value={answers[question.id] ?? ("" as Answer)}
                onChange={(value) => setAnswers((previous) => ({ ...previous, [question.id]: value }))}
              />
            </Card>
          ))}
          <Text style={[styles.muted, { color: palette.foreground }]}>{form.statement}</Text>
          <Pressable
            role="checkbox"
            aria-checked={accepted}
            onPress={() => setAccepted((value) => !value)}
            style={local.check}
          >
            <View
              style={[
                local.box,
                { borderColor: accepted ? palette.primary : palette.border },
                accepted && { backgroundColor: palette.primary },
              ]}
            >
              {accepted && <Text style={{ color: palette.onPrimary, fontWeight: "700" }}>✓</Text>}
            </View>
            <Text style={[local.checkLabel, { color: palette.foreground }]}>{t("accept")}</Text>
          </Pressable>
          <Field
            label={t("signedName")}
            hint={t("signedNameHint")}
            palette={palette}
            value={name}
            onChangeText={setName}
            autoComplete="name"
            textContentType="name"
          />
          <ErrorText message={error} palette={palette} />
          <Button label={t("sign")} palette={palette} busy={busy} onPress={() => void submit()} />
        </>
      )}

      <Button label={t("back")} variant="secondary" palette={palette} onPress={() => router.back()} />
    </Screen>
  );
}

const local = StyleSheet.create({
  check: { flexDirection: "row", alignItems: "center", gap: 12, minHeight: 44 },
  box: { width: 26, height: 26, borderRadius: 6, borderWidth: 2, alignItems: "center", justifyContent: "center" },
  checkLabel: { flex: 1, fontSize: 16, textAlign: "left" },
});
