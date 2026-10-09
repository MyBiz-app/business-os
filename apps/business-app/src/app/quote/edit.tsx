import { addDays, dayOf, formatDay, todayIn } from "@business-os/i18n/dates";
import { toMajorUnits, toMinorUnits } from "@business-os/i18n/money";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { BackBar, PillRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { formatMoney } from "@business-os/app-kit/lib/money";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Line = { description: string; quantity: string; price: string };
const EMPTY: Line = { description: "", quantity: "1", price: "" };
const VALID_FOR = ["0", "7", "14", "30"] as const;

/** A quote written on the phone: a new one for a client (`?client=`) or a draft (`?id=`). Lines,
 * a deposit and how long it's valid; the event's date and place, when set on the web, are kept. */
export default function EditQuote() {
  const params = useLocalSearchParams<{ id?: string; client?: string }>();
  const t = useTranslations("business.quotes");
  const tQuotes = useTranslations("quotes");
  const tBusiness = useTranslations("business");
  const locale = useLocale();
  const { api, scope, tenant, palette } = useBusiness();
  const [title, setTitle] = useState("");
  const [lines, setLines] = useState<Line[]>([EMPTY]);
  const [depositPercent, setDepositPercent] = useState("0");
  const [validUntil, setValidUntil] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const tenantId = tenant?.id;
  const currency = tenant?.currency ?? "ILS";
  const today = todayIn(tenant?.time_zone ?? "UTC");

  const load = useCallback(async () => {
    if (!tenantId) return null;
    const quote = params.id
      ? unwrap(await api.GET("/quotes/{quote_id}", { params: { ...scope, path: { quote_id: params.id } } }))
      : null;
    const clientId = quote?.client_id ?? params.client;
    const client = clientId
      ? unwrap(await api.GET("/clients/{client_id}", { params: { ...scope, path: { client_id: clientId } } }))
      : null;
    return { quote, client };
  }, [api, scope, tenantId, params.id, params.client]);
  const { data } = useLoad(load);

  // A draft fills the form once it has loaded; a new quote starts valid for two weeks.
  const quote = data?.quote;
  useEffect(() => {
    if (!quote) {
      setValidUntil(addDays(today, 14));
      return;
    }
    setTitle(quote.title);
    setLines(
      quote.lines.map((line) => ({
        description: line.description,
        quantity: String(Number(line.quantity)),
        price: toMajorUnits(line.unit_price, quote.currency),
      })),
    );
    setDepositPercent(String(quote.deposit_percent));
    setValidUntil(quote.valid_until ?? null);
    setNotes(quote.notes ?? "");
  }, [quote, today]);

  if (!tenant || !data) return <Screen palette={palette}>{null}</Screen>;
  const client = data.client;
  const clientName = client ? [client.first_name, client.last_name].filter(Boolean).join(" ") : "";

  const parsed = lines.map((line) => ({
    description: line.description.trim(),
    quantity: Number(line.quantity.replace(",", ".")),
    unit_price: toMinorUnits(line.price || "0", currency),
  }));
  const valid = parsed.every((line) => line.description && line.quantity > 0 && line.unit_price !== null);
  const total = parsed.reduce((sum, line) => sum + (line.unit_price ?? 0) * (line.quantity || 0), 0);
  const deposit = Number(depositPercent || "0");

  const update = (index: number, patch: Partial<Line>) =>
    setLines((current) => current.map((line, i) => (i === index ? { ...line, ...patch } : line)));

  // How long the quote is valid: none, or a number of days from today; a draft's own date stays
  // as an extra choice.
  const validOptions = VALID_FOR.map((days) => ({
    value: days === "0" ? "none" : addDays(today, Number(days)),
    label: days === "0" ? t("noEnd") : t("validFor", { count: Number(days) }),
  }));
  if (validUntil && !validOptions.some((option) => option.value === validUntil)) {
    validOptions.push({ value: validUntil, label: formatDay(validUntil, locale, { day: "numeric", month: "short" }) });
  }

  const save = async () => {
    if (!title.trim() || !valid || !(deposit >= 0 && deposit <= 100) || !client) {
      setError(t("invalid"));
      return;
    }
    setSaving(true);
    setError(null);
    // The event, if the draft has one, is sent back as its local date and time.
    const event = quote?.event_starts_at
      ? {
          event_date: dayOf(quote.event_starts_at, tenant.time_zone),
          event_time: new Intl.DateTimeFormat("en-GB", {
            hour: "2-digit",
            minute: "2-digit",
            hourCycle: "h23",
            timeZone: tenant.time_zone,
          }).format(new Date(quote.event_starts_at)),
          event_place: quote.event_place,
        }
      : {};
    const body = {
      title: title.trim(),
      lines: parsed.map((line) => ({ ...line, unit_price: line.unit_price ?? 0 })),
      deposit_percent: Math.round(deposit),
      valid_until: validUntil,
      notes: notes.trim() || null,
      ...event,
    };
    try {
      const saved = quote
        ? unwrap(await api.PUT("/quotes/{quote_id}", { params: { ...scope, path: { quote_id: quote.id } }, body }))
        : unwrap(await api.POST("/quotes", { params: scope, body: { ...body, client_id: client.id } }));
      // A new quote opens on its own screen; an edited draft goes back to the one it came from.
      if (quote) router.back();
      else router.replace(`/quote/${saved.id}?created=1`);
    } catch {
      setError(tBusiness("error"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Screen palette={palette}>
      <BackBar label={clientName || tBusiness("back")} palette={palette} onPress={() => router.back()} />
      <View style={{ gap: 4 }}>
        <Heading palette={palette}>{quote ? tQuotes("edit") : tQuotes("new")}</Heading>
        {clientName ? <Text style={[styles.muted, { color: palette.muted }]}>{t("forClient", { name: clientName })}</Text> : null}
      </View>

      <Field label={tQuotes("titleField")} palette={palette} value={title} onChangeText={setTitle} maxLength={120} placeholder={tQuotes("titleHint")} />

      <Card palette={palette}>
        <SectionTitle title={tQuotes("lines")} palette={palette} />
        {lines.map((line, index) => (
          <View key={index} style={{ gap: 8, borderTopWidth: index ? 1 : 0, borderColor: palette.border, paddingTop: index ? 10 : 0 }}>
            <Field
              label={tQuotes("lineDescription", { number: index + 1 })}
              palette={palette}
              value={line.description}
              onChangeText={(description) => update(index, { description })}
              maxLength={300}
            />
            <View style={{ flexDirection: "row", gap: 8 }}>
              <View style={{ flex: 1 }}>
                <Field
                  label={tQuotes("quantity")}
                  palette={palette}
                  value={line.quantity}
                  onChangeText={(quantity) => update(index, { quantity })}
                  inputMode="decimal"
                />
              </View>
              <View style={{ flex: 2 }}>
                <Field
                  label={tQuotes("unitPrice")}
                  palette={palette}
                  value={line.price}
                  onChangeText={(price) => update(index, { price })}
                  inputMode="decimal"
                  placeholder="0"
                />
              </View>
            </View>
            {lines.length > 1 && (
              <Pressable
                accessibilityRole="button"
                onPress={() => setLines((current) => current.filter((_, i) => i !== index))}
                hitSlop={8}
                style={{ alignSelf: "flex-start", minHeight: 32, justifyContent: "center" }}
              >
                <Text style={{ color: palette.danger, fontWeight: "600" }}>{tQuotes("removeLine", { number: index + 1 })}</Text>
              </Pressable>
            )}
          </View>
        ))}
        <Button label={tQuotes("addLine")} variant="secondary" palette={palette} onPress={() => setLines((current) => [...current, EMPTY])} />
        <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
          <Text style={{ color: palette.foreground, fontWeight: "700" }}>{tQuotes("total")}</Text>
          <Text style={{ color: palette.foreground, fontWeight: "700", fontVariant: ["tabular-nums"] }}>
            {formatMoney(Math.round(total), currency, locale)}
          </Text>
        </View>
      </Card>

      <Field
        label={tQuotes("deposit")}
        palette={palette}
        value={depositPercent}
        onChangeText={setDepositPercent}
        inputMode="numeric"
        hint={tQuotes("depositHint")}
      />
      <Text style={{ color: palette.foreground, fontWeight: "600" }}>{tQuotes("validUntilField")}</Text>
      <PillRow
        label={tQuotes("validUntilField")}
        palette={palette}
        value={validUntil ?? "none"}
        onChange={(value) => setValidUntil(value === "none" ? null : value)}
        options={validOptions}
      />
      <Field
        label={tQuotes("notes")}
        palette={palette}
        value={notes}
        onChangeText={setNotes}
        multiline
        maxLength={4000}
        placeholder={tQuotes("notesHint")}
        style={{ minHeight: 88, paddingTop: 12, textAlignVertical: "top" }}
      />
      <ErrorText message={error} palette={palette} />
      <Button label={tQuotes("saveDraft")} palette={palette} busy={saving} onPress={() => void save()} />
    </Screen>
  );
}
