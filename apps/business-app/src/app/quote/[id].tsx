import type { components } from "@business-os/api-client";
import { dayOf, formatDay, formatTime } from "@business-os/i18n/dates";
import { toMajorUnits, toMinorUnits } from "@business-os/i18n/money";
import { router, useFocusEffect, useLocalSearchParams } from "expo-router";
import { useCallback, useRef, useState } from "react";
import { Linking, Share, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { BackBar, Badge, PillRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { WEB_URL } from "@business-os/app-kit/lib/env";
import { newIdempotencyKey } from "@business-os/app-kit/lib/idempotency";
import { formatMoney } from "@business-os/app-kit/lib/money";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Method = components["schemas"]["StaffPayment"]["method"] & string;
const METHODS: Method[] = ["card", "cash", "transfer", "other"];

/** One quote (or bill) on the go: what's in it, sending it to the client on WhatsApp, recording
 * what they paid, and a new version of a sent one. A draft is edited on its own screen. */
export default function QuoteScreen() {
  const { id, created } = useLocalSearchParams<{ id: string; created?: string }>();
  const t = useTranslations("business.quotes");
  const tQuotes = useTranslations("quotes");
  const tBusiness = useTranslations("business");
  const tMethods = useTranslations("receipts.methods");
  const locale = useLocale();
  const { api, scope, tenant, palette, can } = useBusiness();
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState<Method>("card");
  const [paymentKey, setPaymentKey] = useState(newIdempotencyKey);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(created ? t("saved") : null);
  const [error, setError] = useState<string | null>(null);
  const tenantId = tenant?.id;

  const load = useCallback(async () => {
    if (!tenantId) return null;
    const quote = unwrap(await api.GET("/quotes/{quote_id}", { params: { ...scope, path: { quote_id: id } } }));
    const client = await api
      .GET("/clients/{client_id}", { params: { ...scope, path: { client_id: quote.client_id } } })
      .then(unwrap)
      .catch(() => null);
    return { quote, client };
  }, [api, scope, id, tenantId]);
  const { data, loading, reload } = useLoad(load);
  // Coming back from editing the draft shows it as saved.
  const focused = useRef(false);
  useFocusEffect(
    useCallback(() => {
      if (focused.current) void reload();
      focused.current = true;
    }, [reload]),
  );

  if (!data || !tenant) {
    return (
      <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
        <BackBar label={tBusiness("back")} palette={palette} onPress={() => router.back()} />
      </Screen>
    );
  }

  const { quote, client } = data;
  const money = (value: number) => formatMoney(value, quote.currency, locale);
  const left = quote.total - quote.paid;
  const deposit = Math.round((quote.total * quote.deposit_percent) / 100);
  const link = `${WEB_URL}/q/${quote.token}`;
  const sell = can("sales.manage");
  const shortDay = (day: string) => formatDay(day, locale, { day: "numeric", month: "short", year: "numeric" });
  const message = tQuotes("whatsappText", { name: client?.first_name ?? quote.client_name, title: quote.title, link });
  const digits = client?.phone?.replace(/\D/g, "");

  const act = async (action: () => Promise<string | null>) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const done = await action();
      setNotice(done);
      await reload();
    } catch {
      setError(tBusiness("error"));
    } finally {
      setBusy(false);
    }
  };

  // Sending marks a draft as sent (its link starts to work), then opens WhatsApp with the link.
  const sendOn = (how: "whatsapp" | "share") =>
    act(async () => {
      if (quote.status === "draft") {
        unwrap(await api.POST("/quotes/{quote_id}/send", { params: { ...scope, path: { quote_id: id } } }));
      }
      if (how === "whatsapp") {
        await Linking.openURL(`https://wa.me/${digits ?? ""}?text=${encodeURIComponent(message)}`);
      } else {
        await Share.share({ message }).catch(() => Linking.openURL(link));
      }
      return t("sent");
    });

  const pay = () =>
    act(async () => {
      const suggested = quote.deposit_due > 0 ? quote.deposit_due : left;
      const minor = amount.trim() ? toMinorUnits(amount, quote.currency) : suggested;
      if (!minor || minor > left) {
        throw new Error("invalid amount");
      }
      unwrap(
        await api.POST("/quotes/{quote_id}/payments", {
          params: { ...scope, path: { quote_id: id } },
          body: { amount: minor, method, idempotency_key: paymentKey },
        }),
      );
      setPaymentKey(newIdempotencyKey());
      setAmount("");
      return t("paymentRecorded");
    });

  const copy = () =>
    act(async () => {
      const draft = unwrap(await api.POST("/quotes/{quote_id}/copy", { params: { ...scope, path: { quote_id: id } } }));
      router.replace(`/quote/edit?id=${draft.id}`);
      return null;
    });

  const tone = quote.status === "accepted" ? "success" : quote.status === "declined" || quote.status === "expired" ? "danger" : "muted";
  const title = quote.kind === "bill" ? tQuotes("public.billTitle", { number: quote.number }) : `#${quote.number}`;

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <BackBar label={quote.client_name} palette={palette} onPress={() => router.back()} />
      <View style={{ gap: 6 }}>
        <Heading palette={palette}>{quote.title}</Heading>
        <View style={{ flexDirection: "row", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          <Badge label={tQuotes(`statuses.${quote.status}`)} tone={tone} palette={palette} />
          <Text style={[styles.muted, { color: palette.muted }]}>
            {[title, quote.client_name].join(" · ")}
          </Text>
        </View>
      </View>

      <View accessibilityLiveRegion="polite">
        {notice ? <Text style={{ color: palette.success, fontWeight: "600" }}>{notice}</Text> : null}
        <ErrorText message={error} palette={palette} />
      </View>

      <Card palette={palette}>
        <SectionTitle title={tQuotes("lines")} palette={palette} />
        {quote.lines.map((line, index) => {
          const quantity = Number(line.quantity);
          return (
            <View key={index} style={{ flexDirection: "row", gap: 8, alignItems: "flex-start" }}>
              <View style={{ flex: 1, gap: 2 }}>
                <Text style={{ color: palette.foreground, textAlign: "left" }}>{line.description}</Text>
                {quantity !== 1 && (
                  <Text style={{ color: palette.muted, fontSize: 13, textAlign: "left" }}>
                    {`${new Intl.NumberFormat(locale).format(quantity)} × ${money(line.unit_price)}`}
                  </Text>
                )}
              </View>
              <Text style={{ color: palette.foreground, fontWeight: "600", fontVariant: ["tabular-nums"] }}>
                {money(Math.round(quantity * line.unit_price))}
              </Text>
            </View>
          );
        })}
        <View style={{ flexDirection: "row", justifyContent: "space-between", borderTopWidth: 1, borderColor: palette.border, paddingTop: 8 }}>
          <Text style={{ color: palette.foreground, fontWeight: "700" }}>{tQuotes("total")}</Text>
          <Text style={{ color: palette.foreground, fontWeight: "700", fontVariant: ["tabular-nums"] }}>{money(quote.total)}</Text>
        </View>
        {quote.deposit_percent > 0 && (
          <Text style={[styles.muted, { color: palette.muted }]}>
            {tQuotes("depositOf", { percent: quote.deposit_percent, amount: money(deposit) })}
          </Text>
        )}
        {quote.paid > 0 && (
          <Text style={{ color: palette.foreground, textAlign: "left" }}>
            {[tQuotes("paidSoFar", { amount: money(quote.paid) }), left > 0 ? tQuotes("balance", { amount: money(left) }) : tQuotes("fullyPaid")].join(" · ")}
          </Text>
        )}
        {quote.event_starts_at && (
          <Text style={{ color: palette.foreground, textAlign: "left" }}>
            {[
              `${tQuotes("event")}: ${shortDay(dayOf(quote.event_starts_at, tenant.time_zone))} ${formatTime(quote.event_starts_at, locale, tenant.time_zone)}`,
              quote.event_place,
            ]
              .filter(Boolean)
              .join(" · ")}
          </Text>
        )}
        {quote.valid_until && quote.status !== "accepted" && (
          <Text style={[styles.muted, { color: palette.muted }]}>{tQuotes("validUntil", { date: shortDay(quote.valid_until) })}</Text>
        )}
        {quote.accepted_name && quote.accepted_at && (
          <Text style={{ color: palette.success, textAlign: "left" }}>
            {tQuotes("acceptedBy", { name: quote.accepted_name, date: shortDay(dayOf(quote.accepted_at, tenant.time_zone)) })}
          </Text>
        )}
        {quote.notes ? <Text style={[styles.muted, { color: palette.muted }]}>{quote.notes}</Text> : null}
      </Card>

      {sell && (quote.status === "draft" || quote.status === "sent") && (
        <Card palette={palette}>
          <SectionTitle title={quote.status === "draft" ? tQuotes("send") : t("sendAgain")} palette={palette} />
          {quote.status === "draft" && <Text style={[styles.muted, { color: palette.muted }]}>{tQuotes("draftHint")}</Text>}
          <Button label={t("whatsapp")} palette={palette} busy={busy} onPress={() => void sendOn("whatsapp")} />
          <Button label={t("share")} variant="secondary" palette={palette} busy={busy} onPress={() => void sendOn("share")} />
          {quote.status === "draft" ? (
            <Button label={tQuotes("edit")} variant="secondary" palette={palette} onPress={() => router.push(`/quote/edit?id=${id}`)} />
          ) : (
            <Button label={tQuotes("copyAsNew")} variant="secondary" palette={palette} busy={busy} onPress={() => void copy()} />
          )}
        </Card>
      )}

      {sell && quote.status === "accepted" && left > 0 && (
        <Card palette={palette}>
          <SectionTitle title={tQuotes("recordPayment")} palette={palette} />
          <Text style={{ color: palette.foreground, textAlign: "left" }}>{tQuotes("leftToPay", { amount: money(left) })}</Text>
          <Field
            label={tQuotes("amount")}
            palette={palette}
            value={amount}
            onChangeText={setAmount}
            inputMode="decimal"
            placeholder={toMajorUnits(quote.deposit_due > 0 ? quote.deposit_due : left, quote.currency)}
            hint={quote.deposit_due > 0 ? t("depositDue", { amount: money(quote.deposit_due) }) : undefined}
          />
          <PillRow<Method>
            label={tQuotes("method")}
            palette={palette}
            value={method}
            onChange={setMethod}
            options={METHODS.map((value) => ({ value, label: tMethods(value) }))}
          />
          <Button label={tQuotes("recordPayment")} palette={palette} busy={busy} onPress={() => void pay()} />
        </Card>
      )}

      {quote.status !== "draft" && (
        <Button label={tQuotes("preview")} variant="secondary" palette={palette} onPress={() => void Linking.openURL(link)} />
      )}
    </Screen>
  );
}
