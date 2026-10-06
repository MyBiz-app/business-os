import type { components } from "@business-os/api-client";
import { dayOf, formatDay, formatTime } from "@business-os/i18n/dates";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useState } from "react";
import { Linking, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Avatar, BackBar, Badge, ListRow, PillRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { newIdempotencyKey } from "@business-os/app-kit/lib/idempotency";
import { formatMoney } from "@business-os/app-kit/lib/money";
import { fullName } from "@business-os/app-kit/lib/names";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { termsFor } from "@business-os/app-kit/lib/vertical";
import { useBusiness } from "@/providers/business-provider";

type Method = components["schemas"]["Sale"]["method"] & string;
type Panel = "sell" | "note" | "message" | null;

const METHODS: Method[] = ["card", "cash", "transfer", "other"];
const VISITS_SHOWN = 5;
const NOTES_SHOWN = 5;

/** One client on the go: how to reach them, their plans (and selling one), what's coming up,
 * their last visits, the team's notes and a message. Each part follows the person's permissions. */
export default function ClientScreen() {
  const { id, created } = useLocalSearchParams<{ id: string; created?: string }>();
  const t = useTranslations("business.clients");
  const tBusiness = useTranslations("business");
  const tMessages = useTranslations("business.messages");
  const tBookings = useTranslations("bookings");
  const tPlans = useTranslations("plans");
  const tNotes = useTranslations("visitNotes");
  const tMethods = useTranslations("receipts.methods");
  const tStatus = useTranslations("clients.statuses");
  const tMessaging = useTranslations("messaging");
  const tTerms = useTranslations("terms");
  const locale = useLocale();
  const { api, scope, tenant, palette, can } = useBusiness();
  const [panel, setPanel] = useState<Panel>(null);
  const [planId, setPlanId] = useState<string | null>(null);
  const [method, setMethod] = useState<Method>("card");
  const [saleKey, setSaleKey] = useState(newIdempotencyKey);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(created ? t("created") : null);
  const [error, setError] = useState<string | null>(null);
  const tenantId = tenant?.id;
  const messaging = tenant?.modules.includes("whatsapp") ?? false;

  const load = useCallback(async () => {
    if (!tenantId) return null;
    const path = { client_id: id };
    const [client, bookings, entitlements, notes, plans] = await Promise.all([
      api.GET("/clients/{client_id}", { params: { ...scope, path } }).then(unwrap),
      api.GET("/clients/{client_id}/bookings", { params: { ...scope, path } }).then(unwrap),
      api
        .GET("/clients/{client_id}/entitlements", { params: { ...scope, path } })
        .then(unwrap)
        .catch(() => []),
      api
        .GET("/clients/{client_id}/notes", { params: { ...scope, path } })
        .then(unwrap)
        .catch(() => []),
      can("sales.manage")
        ? api
            .GET("/plans", { params: { ...scope, query: { active: true } } })
            .then(unwrap)
            .catch(() => [])
        : Promise.resolve([]),
    ]);
    return { client, bookings, entitlements, notes, plans };
  }, [api, scope, id, tenantId, can]);
  const { data, loading, reload } = useLoad(load);

  const act = async (action: () => Promise<string>) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const done = await action();
      setPanel(null);
      setText("");
      setNotice(done);
      await reload();
    } catch {
      setError(tBusiness("error"));
    } finally {
      setBusy(false);
    }
  };

  if (!data || !tenant) {
    return (
      <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
        <BackBar label={tTerms(`${termsFor(tenant)}.clients`)} palette={palette} onPress={() => router.back()} />
      </Screen>
    );
  }

  const { client, bookings, entitlements, notes, plans } = data;
  const name = fullName(client.first_name, client.last_name);
  const timeZone = tenant.time_zone;
  const now = Date.now();
  const visits = bookings.filter((b) => b.status === "checked_in");
  const past = bookings.filter((b) => Date.parse(b.starts_at) <= now && b.status !== "cancelled").slice(0, VISITS_SHOWN);
  const upcoming = bookings
    .filter((b) => Date.parse(b.starts_at) > now && (b.status === "booked" || b.status === "waitlisted"))
    .sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  const active = entitlements.filter((e) => e.state === "active" || e.state === "upcoming" || e.state === "frozen");
  const digits = client.phone?.replace(/\D/g, "");
  const short = (instant: string) =>
    `${formatDay(dayOf(instant, timeZone), locale, { weekday: "short", day: "numeric", month: "short" })} ${formatTime(instant, locale, timeZone)}`;
  const chosen = plans.find((p) => p.id === planId) ?? plans[0];

  const sell = () =>
    act(async () => {
      if (!chosen) return "";
      unwrap(
        await api.POST("/clients/{client_id}/entitlements", {
          params: { ...scope, path: { client_id: id } },
          body: { plan_id: chosen.id, method, idempotency_key: saleKey },
        }),
      );
      setSaleKey(newIdempotencyKey());
      return t("sold", { plan: chosen.name });
    });

  const addNote = () =>
    act(async () => {
      unwrap(await api.POST("/clients/{client_id}/notes", { params: { ...scope, path: { client_id: id } }, body: { body: text } }));
      return t("noteSaved");
    });

  const send = () =>
    act(async () => {
      unwrap(await api.POST("/messages/direct", { params: scope, body: { client_id: id, channel: "whatsapp", body: text } }));
      return tMessaging("sentOne");
    });

  const toggle = (next: Panel) => {
    setPanel(panel === next ? null : next);
    setText("");
    setError(null);
  };

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <BackBar label={tTerms(`${termsFor(tenant)}.clients`)} palette={palette} onPress={() => router.back()} />

      <View style={{ flexDirection: "row", alignItems: "center", gap: 14 }}>
        <Avatar name={name} palette={palette} size={56} />
        <View style={{ flex: 1, gap: 4 }}>
          <Heading palette={palette}>{name}</Heading>
          <View style={{ flexDirection: "row", gap: 6, flexWrap: "wrap" }}>
            <Badge
              label={tStatus(client.status)}
              tone={client.status === "active" ? "success" : "muted"}
              palette={palette}
            />
            <Badge label={t("visits", { count: visits.length })} palette={palette} />
          </View>
        </View>
      </View>
      <Text style={[styles.muted, { color: palette.muted }]}>
        {visits[0]
          ? t("lastVisit", { date: formatDay(dayOf(visits[0].starts_at, timeZone), locale, { day: "numeric", month: "short" }) })
          : t("neverVisited")}
        {client.phone ? ` · ${client.phone}` : ""}
      </Text>

      <View accessibilityLiveRegion="polite">
        {notice ? <Text style={{ color: palette.success, fontWeight: "600" }}>{notice}</Text> : null}
        <ErrorText message={error} palette={palette} />
      </View>

      {(client.phone || client.email) && (
        <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
          {client.phone && (
            <View style={{ flexGrow: 1, flexBasis: "30%" }}>
              <Button label={t("call")} palette={palette} onPress={() => void Linking.openURL(`tel:${client.phone}`)} />
            </View>
          )}
          {client.phone && (
            <View style={{ flexGrow: 1, flexBasis: "30%" }}>
              <Button
                label={t("whatsapp")}
                variant="secondary"
                palette={palette}
                onPress={() => void Linking.openURL(`https://wa.me/${digits}`)}
              />
            </View>
          )}
          {client.email && (
            <View style={{ flexGrow: 1, flexBasis: "30%" }}>
              <Button
                label={t("email")}
                variant="secondary"
                palette={palette}
                onPress={() => void Linking.openURL(`mailto:${client.email}`)}
              />
            </View>
          )}
        </View>
      )}

      <Card palette={palette}>
        <SectionTitle
          title={t("plan")}
          action={can("sales.manage") ? t("sell") : undefined}
          onAction={() => toggle("sell")}
          palette={palette}
        />
        {active.length === 0 ? (
          <Text style={[styles.muted, { color: palette.muted }]}>{t("noPlan")}</Text>
        ) : (
          active.map((plan) => (
            <View key={plan.id} style={{ gap: 2 }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                <Text style={{ color: palette.foreground, fontWeight: "600", flex: 1, textAlign: "left" }}>{plan.name}</Text>
                <Badge
                  label={tPlans(`states.${plan.state}`)}
                  tone={plan.state === "active" ? "success" : "muted"}
                  palette={palette}
                />
              </View>
              <Text style={[styles.muted, { color: palette.muted }]}>
                {tPlans("validityRange", {
                  from: formatDay(plan.starts_on, locale, { day: "numeric", month: "short" }),
                  to: formatDay(plan.ends_on, locale, { day: "numeric", month: "short" }),
                })}
                {plan.credits !== null && plan.credits_remaining !== null
                  ? ` · ${t("credits", { left: plan.credits_remaining, total: plan.credits })}`
                  : ""}
              </Text>
            </View>
          ))
        )}
        {panel === "sell" &&
          (plans.length === 0 ? (
            <Text style={[styles.muted, { color: palette.muted }]}>{t("noPlans")}</Text>
          ) : (
            <View style={{ gap: 10 }}>
              <Text style={{ color: palette.foreground, fontWeight: "600" }}>{tPlans("plan")}</Text>
              {plans.map((plan) => {
                const selected = plan.id === chosen?.id;
                return (
                  <ListRow
                    key={plan.id}
                    palette={palette}
                    title={plan.name}
                    subtitle={
                      plan.credits ? tPlans("creditsCount", { count: plan.credits }) : tPlans("days", { count: plan.validity_days })
                    }
                    accessibilityLabel={[plan.name, formatMoney(plan.price_amount, plan.price_currency, locale), selected ? t("selected") : null]
                      .filter(Boolean)
                      .join(", ")}
                    trailing={
                      <View style={{ alignItems: "flex-end", gap: 4 }}>
                        <Text style={{ color: palette.foreground, fontWeight: "700" }}>
                          {formatMoney(plan.price_amount, plan.price_currency, locale)}
                        </Text>
                        {selected && <Badge label={t("selected")} tone="primary" palette={palette} />}
                      </View>
                    }
                    onPress={() => setPlanId(plan.id)}
                  />
                );
              })}
              <Text style={{ color: palette.foreground, fontWeight: "600" }}>{tPlans("paymentMethod")}</Text>
              <PillRow<Method>
                label={tPlans("paymentMethod")}
                palette={palette}
                value={method}
                onChange={setMethod}
                options={METHODS.map((value) => ({ value, label: tMethods(value) }))}
              />
              <Text style={[styles.muted, { color: palette.muted }]}>{tPlans("simulatedPayment")}</Text>
              {chosen && (
                <Button
                  label={`${tPlans("sell")} · ${formatMoney(chosen.price_amount, chosen.price_currency, locale)}`}
                  palette={palette}
                  busy={busy}
                  onPress={() => void sell()}
                />
              )}
            </View>
          ))}
      </Card>

      {upcoming.length > 0 && (
        <View style={{ gap: 8 }}>
          <SectionTitle title={t("upcomingTitle")} palette={palette} />
          {upcoming.map((booking) => (
            <ListRow
              key={booking.id}
              palette={palette}
              title={booking.service_name}
              subtitle={short(booking.starts_at)}
              trailing={<Badge label={tBookings(`statuses.${booking.status}`)} tone="primary" palette={palette} />}
              onPress={() => router.push(`/session/${booking.session_id}`)}
            />
          ))}
        </View>
      )}

      <View style={{ gap: 8 }}>
        <SectionTitle title={t("visitsTitle")} palette={palette} />
        {past.length === 0 ? (
          <Text style={[styles.muted, { color: palette.muted }]}>{t("noVisits")}</Text>
        ) : (
          past.map((booking) => (
            <ListRow
              key={booking.id}
              palette={palette}
              title={booking.service_name}
              subtitle={short(booking.starts_at)}
              trailing={
                <Badge
                  label={tBookings(`statuses.${booking.status}`)}
                  tone={booking.status === "checked_in" ? "success" : booking.status === "no_show" ? "danger" : "muted"}
                  palette={palette}
                />
              }
            />
          ))
        )}
      </View>

      <Card palette={palette}>
        <SectionTitle
          title={tTerms(`${termsFor(tenant)}.visitNotes`)}
          action={can("clients.write") || can("bookings.manage") ? tNotes("add") : undefined}
          onAction={() => toggle("note")}
          palette={palette}
        />
        {panel === "note" && (
          <View style={{ gap: 8 }}>
            <Field
              label={tNotes("body")}
              palette={palette}
              value={text}
              onChangeText={setText}
              multiline
              style={{ minHeight: 88, paddingTop: 12, textAlignVertical: "top" }}
            />
            <Button label={tNotes("add")} palette={palette} busy={busy} disabled={!text.trim()} onPress={() => void addNote()} />
          </View>
        )}
        {client.notes ? <Text style={[styles.muted, { color: palette.foreground }]}>{client.notes}</Text> : null}
        {notes.length === 0 && !client.notes ? (
          <Text style={[styles.muted, { color: palette.muted }]}>{tNotes("none")}</Text>
        ) : (
          notes.slice(0, NOTES_SHOWN).map((note) => (
            <View key={note.id} style={{ gap: 2, borderTopWidth: 1, borderColor: palette.border, paddingTop: 8 }}>
              <Text style={{ color: palette.foreground, textAlign: "left" }}>{note.body}</Text>
              <Text style={{ color: palette.muted, fontSize: 13, textAlign: "left" }}>
                {[note.author_name, note.service_name, short(note.created_at)].filter(Boolean).join(" · ")}
              </Text>
            </View>
          ))
        )}
      </Card>

      {messaging && can("clients.write") && client.phone && (
        <Card palette={palette}>
          <SectionTitle title={tMessages("title")} action={t("message")} onAction={() => toggle("message")} palette={palette} />
          {panel === "message" ? (
            <View style={{ gap: 8 }}>
              <Field
                label={tMessages("to", { name })}
                palette={palette}
                value={text}
                onChangeText={setText}
                multiline
                maxLength={1000}
                style={{ minHeight: 88, paddingTop: 12, textAlignVertical: "top" }}
              />
              <Text style={[styles.muted, { color: palette.muted }]}>{tMessaging("simulated")}</Text>
              <Button label={tMessages("send")} palette={palette} busy={busy} disabled={!text.trim()} onPress={() => void send()} />
            </View>
          ) : (
            <Text style={[styles.muted, { color: palette.muted }]}>{tMessaging("subtitle")}</Text>
          )}
        </Card>
      )}
    </Screen>
  );
}
