import type { components } from "@business-os/api-client";
import { addDays, addMonths, formatDay, todayIn } from "@business-os/i18n/dates";
import { formatMoney } from "@business-os/app-kit/lib/money";
import * as ImagePicker from "expo-image-picker";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { StyleSheet, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { MonthGrid } from "@business-os/app-kit/components/calendar-strip";
import { Chip } from "@business-os/app-kit/components/chip";
import { BackBar, Badge, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Field, Heading, LoadError, Screen, styles } from "@business-os/app-kit/components/ui";
import { ApiError, unwrap } from "@business-os/app-kit/lib/api";
import { confirm } from "@business-os/app-kit/lib/confirm";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Reason = components["schemas"]["FreezeRequestCreate"]["reason"];
type Preview = components["schemas"]["FreezePreview"];
type Request = components["schemas"]["FreezeRequest"];

const REASONS: Reason[] = ["travel", "reserve_duty", "illness", "pregnancy", "other"];
const NO_DAYS: ReadonlySet<string> = new Set();
const STATUS_TONE = { pending: "primary", approved: "success", rejected: "danger", cancelled: "muted" } as const;

/** Freeze my membership: pick the days and a reason, see exactly what will happen, send the
 * request. Also: end a running freeze early, and follow my requests. */
export default function FreezeScreen() {
  const { entitlement: entitlementId } = useLocalSearchParams<{ entitlement?: string }>();
  const t = useTranslations("client.freeze");
  const tFreeze = useTranslations("freeze");
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();

  const [start, setStart] = useState<string | null>(null);
  const [end, setEnd] = useState<string | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [reason, setReason] = useState<Reason>("travel");
  const [note, setNote] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [paper, setPaper] = useState<{ id: string; name: string } | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(async () => {
    const [entitlements, rules, requests] = await Promise.all([
      api.GET("/client/entitlements", { params: scope }).then(unwrap),
      api.GET("/client/freeze-rules", { params: scope }).then(unwrap),
      api.GET("/client/freeze-requests", { params: scope }).then(unwrap),
    ]);
    return { entitlement: entitlements.find((e) => e.id === entitlementId), rules, requests };
  }, [api, scope, entitlementId]);
  const { data, error, loading, reload } = useLoad(load);

  const today = business ? todayIn(business.time_zone) : "";
  const anchor = cursor ?? start ?? today;

  // Show what the freeze would do as soon as both days are picked.
  useEffect(() => {
    setPreview(null);
    if (!entitlementId || !start || !end) return;
    let current = true;
    void api
      .GET("/client/entitlements/{entitlement_id}/freeze-preview", {
        params: { ...scope, path: { entitlement_id: entitlementId }, query: { starts_on: start, ends_on: end, reason } },
      })
      .then((response) => {
        if (current && response.data) setPreview(response.data);
      });
    return () => {
      current = false;
    };
  }, [api, scope, entitlementId, start, end, reason]);

  const marked = useMemo(() => {
    if (!start) return NO_DAYS;
    const days = new Set<string>();
    for (let day = start; day <= (end ?? start); day = addDays(day, 1)) days.add(day);
    return days;
  }, [start, end]);

  if (!business) return null;
  const money = (amount: number) => formatMoney(amount, business.currency, locale);
  const show = (day: string) => formatDay(day, locale, { day: "numeric", month: "short" });
  const entitlement = data?.entitlement;

  const pick = (day: string) => {
    setMessage(null);
    if (!start || end) {
      setStart(day);
      setEnd(null);
    } else if (day < start) {
      setStart(day);
    } else {
      setEnd(day);
    }
  };

  const problemText = (code: string) => (code in PROBLEMS ? tFreeze(`problems.${PROBLEMS[code]}`) : tFreeze("problems.generic"));

  /** A photo of a medical note or call-up paper goes to my documents first; the request points at it. */
  const attach = async (result: ImagePicker.ImagePickerResult) => {
    const asset = result.canceled ? null : result.assets[0];
    if (!asset) return;
    setBusy(true);
    setMessage(null);
    try {
      const form = new FormData();
      const name = asset.fileName ?? "freeze-paper.jpg";
      if (asset.file) form.append("file", asset.file);
      else form.append("file", { uri: asset.uri, name, type: asset.mimeType ?? "image/jpeg" } as unknown as Blob);
      const saved = unwrap(await api.POST("/client/documents", { params: scope, body: form as never, bodySerializer: (body) => body }));
      setPaper({ id: saved.id, name: saved.name });
    } catch {
      setMessage({ ok: false, text: t("paperFailed") });
    } finally {
      setBusy(false);
    }
  };
  const photoOptions: ImagePicker.ImagePickerOptions = { mediaTypes: ["images"], quality: 0.7 };
  const paperFromGallery = async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) return setMessage({ ok: false, text: t("paperPermission") });
    await attach(await ImagePicker.launchImageLibraryAsync(photoOptions));
  };
  const paperFromCamera = async () => {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) return setMessage({ ok: false, text: t("paperPermission") });
    await attach(await ImagePicker.launchCameraAsync(photoOptions));
  };

  const send = async () => {
    if (!entitlementId || !start || !end) return;
    setBusy(true);
    setMessage(null);
    try {
      const sent = unwrap(
        await api.POST("/client/entitlements/{entitlement_id}/freeze-requests", {
          params: { ...scope, path: { entitlement_id: entitlementId } },
          body: { starts_on: start, ends_on: end, reason, note: note.trim() || null, document_id: paper?.id ?? null },
        }),
      );
      setMessage({ ok: true, text: sent.status === "approved" ? t("done") : t("sent") });
      setStart(null);
      setEnd(null);
      setNote("");
      setPaper(null);
      await reload();
    } catch (caught) {
      setMessage({ ok: false, text: problemText(caught instanceof ApiError ? (caught.detail ?? "") : "") });
    } finally {
      setBusy(false);
    }
  };

  const withdraw = async (request: Request) => {
    unwrap(
      await api.DELETE("/client/freeze-requests/{request_id}", { params: { ...scope, path: { request_id: request.id } } }),
    );
    await reload();
  };

  const backEarly = async (freezeId: string) => {
    if (!(await confirm(t("backEarlyTitle"), t("backEarlyMessage"), t("backEarly"), t("keep")))) return;
    try {
      unwrap(await api.POST("/client/freezes/{freeze_id}/end-early", { params: { ...scope, path: { freeze_id: freezeId } } }));
      setMessage({ ok: true, text: t("backEarlyDone") });
      await reload();
    } catch (caught) {
      setMessage({ ok: false, text: problemText(caught instanceof ApiError ? (caught.detail ?? "") : "") });
    }
  };

  const running = entitlement?.freezes.filter((f) => f.ends_on >= today) ?? [];
  const bank = data?.rules.bank;

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <BackBar label={t("backTo")} palette={palette} onPress={() => router.back()} />
      <Heading palette={palette}>{t("title")}</Heading>
      {error !== undefined && !data && <LoadError palette={palette} onRetry={() => void reload()} />}
      {entitlement && <Text style={[local.meta, { color: palette.muted }]}>{entitlement.name}</Text>}

      {running.map((freeze) => (
        <Card key={freeze.id} palette={palette}>
          <Text style={[local.name, { color: palette.foreground }]}>
            {t("frozenRange", { from: show(freeze.starts_on), to: show(freeze.ends_on) })}
          </Text>
          <Button label={t("backEarly")} variant="secondary" palette={palette} onPress={() => void backEarly(freeze.id)} />
        </Card>
      ))}

      {data && !data.rules.rules.allow_requests && (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.foreground }]}>{t("off")}</Text>
        </Card>
      )}

      {data && data.rules.rules.allow_requests && entitlement?.freezable && (
        <>
          {bank?.remaining_days !== null && bank?.remaining_days !== undefined && bank.yearly_bank_days !== null && (
            <Badge
              label={t("bank", { remaining: bank.remaining_days, total: bank.yearly_bank_days })}
              tone="primary"
              palette={palette}
            />
          )}
          <Card palette={palette}>
            <Text style={[local.meta, { color: palette.foreground }]}>{!start || end ? t("pickStart") : t("pickEnd")}</Text>
            <View style={local.monthBar}>
              <Button label="‹" accessibilityLabel={formatDay(addMonths(anchor, -1), locale, { month: "long" })} variant="secondary" palette={palette} onPress={() => setCursor(addMonths(anchor, -1))} />
              <Text style={[local.name, { color: palette.foreground }]}>{formatDay(anchor, locale, { month: "long", year: "numeric" })}</Text>
              <Button label="›" accessibilityLabel={formatDay(addMonths(anchor, 1), locale, { month: "long" })} variant="secondary" palette={palette} onPress={() => setCursor(addMonths(anchor, 1))} />
            </View>
            <MonthGrid selected={anchor} today={today} marked={marked} closed={NO_DAYS} onPick={pick} palette={palette} />
            {start && end && (
              <Text style={[local.name, { color: palette.foreground }]}>
                {t("range", { from: show(start), to: show(end), days: preview?.days ?? 0 })}
              </Text>
            )}
          </Card>

          <SectionTitle title={t("reason")} palette={palette} />
          <View style={local.chips}>
            {REASONS.map((value) => (
              <Chip key={value} label={tFreeze(`reasons.${value}`)} selected={reason === value} onPress={() => setReason(value)} palette={palette} />
            ))}
          </View>
          <Field label={t("note")} palette={palette} value={note} onChangeText={setNote} maxLength={500} multiline />

          <SectionTitle title={t("paper")} palette={palette} />
          <Text style={[local.meta, { color: palette.muted }]}>{t("paperHint")}</Text>
          {paper ? (
            <View style={local.row}>
              <Text style={[local.name, local.info, { color: palette.foreground }]}>{paper.name}</Text>
              <Button label={t("paperRemove")} variant="secondary" palette={palette} onPress={() => setPaper(null)} />
            </View>
          ) : (
            <View style={local.chips}>
              <Button label={t("paperGallery")} variant="secondary" palette={palette} busy={busy} onPress={() => void paperFromGallery()} />
              <Button label={t("paperCamera")} variant="secondary" palette={palette} busy={busy} onPress={() => void paperFromCamera()} />
            </View>
          )}

          {preview && (
            <Card palette={palette}>
              <Text style={[local.name, { color: palette.foreground }]}>{t("whatHappens")}</Text>
              {preview.problems.map((code) => (
                <ErrorText key={code} message={problemText(code)} palette={palette} />
              ))}
              {preview.problems.length === 0 && (
                <>
                  <Text style={[local.meta, { color: palette.foreground }]}>{t("newEnd", { date: show(preview.new_ends_on) })}</Text>
                  {preview.billing_mode === "defer" && preview.next_billing_from && preview.next_billing_to && (
                    <Text style={[local.meta, { color: palette.foreground }]}>
                      {t("shift", { from: show(preview.next_billing_from), to: show(preview.next_billing_to) })}
                    </Text>
                  )}
                  {preview.credit_amount > 0 && <Text style={[local.meta, { color: palette.foreground }]}>{t("credit", { amount: money(preview.credit_amount) })}</Text>}
                  {preview.fee_amount > 0 && <Text style={[local.meta, { color: palette.foreground }]}>{t("fee", { amount: money(preview.fee_amount) })}</Text>}
                  {preview.next_billing_amount_after !== null && (
                    <Text style={[local.meta, { color: palette.foreground }]}>{t("nextAmount", { amount: money(preview.next_billing_amount_after) })}</Text>
                  )}
                  <Text style={[local.meta, { color: palette.muted }]}>{preview.auto_approved ? t("auto") : t("manual")}</Text>
                </>
              )}
            </Card>
          )}
          {message && (
            <Text accessibilityRole={message.ok ? undefined : "alert"} accessibilityLiveRegion="polite" style={[local.meta, { color: message.ok ? palette.primaryInk : palette.danger }]}>
              {message.text}
            </Text>
          )}
          <Button
            label={preview?.auto_approved ? t("sendNow") : t("send")}
            palette={palette}
            busy={busy}
            disabled={!start || !end || busy || (preview?.problems.length ?? 0) > 0}
            onPress={() => void send()}
          />
        </>
      )}

      {message && !(data?.rules.rules.allow_requests && entitlement?.freezable) && (
        <Text accessibilityLiveRegion="polite" style={[local.meta, { color: message.ok ? palette.primaryInk : palette.danger }]}>
          {message.text}
        </Text>
      )}

      {data && data.requests.length > 0 && (
        <>
          <Heading palette={palette} level={2}>
            {t("myRequests")}
          </Heading>
          <Card palette={palette}>
            {data.requests.map((request) => (
              <View key={request.id} style={local.row}>
                <View style={local.info}>
                  <Text style={[local.name, { color: palette.foreground }]}>
                    {t("range", { from: show(request.starts_on), to: show(request.ends_on), days: request.days })}
                  </Text>
                  <Text style={[local.meta, { color: palette.muted }]}>
                    {request.entitlement_name} · {tFreeze(`reasons.${request.reason}`)}
                    {request.document_id ? ` · ${t("paperAttached")}` : ""}
                  </Text>
                  {request.decision_note ? <Text style={[local.meta, { color: palette.muted }]}>{request.decision_note}</Text> : null}
                </View>
                <Badge label={tFreeze(`status.${request.status}`)} tone={STATUS_TONE[request.status]} palette={palette} />
                {request.status === "pending" && (
                  <Button label={t("withdraw")} variant="secondary" palette={palette} onPress={() => void withdraw(request)} />
                )}
              </View>
            ))}
          </Card>
        </>
      )}
    </Screen>
  );
}

/** The API's refusal codes the app words itself (anything else gets the general message). */
const PROBLEMS: Record<string, "freeze_requests_off" | "not_freezable" | "too_short" | "too_long" | "notice_required" | "outside_validity" | "overlapping_freeze" | "overlapping_request" | "bank_exceeded"> = {
  freeze_requests_off: "freeze_requests_off",
  not_freezable: "not_freezable",
  too_short: "too_short",
  too_long: "too_long",
  notice_required: "notice_required",
  outside_validity: "outside_validity",
  overlapping_freeze: "overlapping_freeze",
  overlapping_request: "overlapping_request",
  bank_exceeded: "bank_exceeded",
};

const local = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 8, flexWrap: "wrap" },
  info: { flex: 1, gap: 2, minWidth: 160 },
  name: { fontSize: 15, fontWeight: "500", textAlign: "left" },
  meta: { fontSize: 13, textAlign: "left" },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  monthBar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
});
