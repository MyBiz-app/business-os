import type { components } from "@business-os/api-client";
import { dayOf, formatDay, formatTime } from "@business-os/i18n/dates";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useState } from "react";
import { Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Avatar, BackBar, Badge, ListRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { ApiError, unwrap } from "@business-os/app-kit/lib/api";
import { confirm } from "@business-os/app-kit/lib/confirm";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Booking = components["schemas"]["Booking"];
type ClientListItem = components["schemas"]["ClientListItem"];

const TONE = { checked_in: "success", no_show: "danger", waitlisted: "primary" } as const;
const BOOKING_ERRORS = ["already_booked", "session_cancelled", "invalid_transition", "invalid_reference", "not_found"];

/** One session: who's coming, check-in, booking someone in and a note about a visit. */
export default function SessionScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const t = useTranslations("business.today");
  const tSession = useTranslations("business.session");
  const tBookings = useTranslations("bookings");
  const tNotes = useTranslations("visitNotes");
  const locale = useLocale();
  const { api, scope, tenant, palette, can } = useBusiness();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [search, setSearch] = useState("");
  const [matches, setMatches] = useState<ClientListItem[] | null>(null);
  const [noteFor, setNoteFor] = useState<Booking | null>(null);
  const [note, setNote] = useState("");
  const timeZone = tenant?.time_zone ?? "UTC";
  const manage = can("bookings.manage");

  const tenantId = tenant?.id;
  const load = useCallback(async () => {
    if (!tenantId) return null; // a link opened before the business is known
    const [session, bookings] = await Promise.all([
      api.GET("/sessions/{session_id}", { params: { ...scope, path: { session_id: id } } }).then(unwrap),
      api.GET("/sessions/{session_id}/bookings", { params: { ...scope, path: { session_id: id } } }).then(unwrap),
    ]);
    return { session, bookings };
  }, [api, scope, id, tenantId]);
  const { data, loading, reload } = useLoad(load);

  const fail = (caught: unknown) => {
    const code = caught instanceof ApiError ? caught.detail : undefined;
    setError(code && BOOKING_ERRORS.includes(code) ? tBookings(`errors.${code}`) : tBookings("errors.generic"));
  };

  const run = async (key: string, action: () => Promise<void>) => {
    setBusy(key);
    setError(null);
    setNotice(null);
    try {
      await action();
      await reload();
    } catch (caught) {
      fail(caught);
    } finally {
      setBusy(null);
    }
  };

  const setStatus = (booking: Booking, status: "checked_in" | "no_show" | "booked") =>
    run(booking.id, async () => {
      unwrap(
        await api.PATCH("/bookings/{booking_id}", { params: { ...scope, path: { booking_id: booking.id } }, body: { status } }),
      );
    });

  const cancel = async (booking: Booking) => {
    const yes = await confirm(
      tSession("cancel"),
      tSession("cancelConfirm", { name: booking.client_name }),
      tSession("yes"),
      tSession("no"),
    );
    if (!yes) return;
    await run(booking.id, async () => {
      unwrap(
        await api.PATCH("/bookings/{booking_id}", {
          params: { ...scope, path: { booking_id: booking.id } },
          body: { status: "cancelled" },
        }),
      );
    });
  };

  const find = async () => {
    setError(null);
    try {
      const page = unwrap(
        await api.GET("/clients", { params: { ...scope, query: { search: search.trim() || undefined, status: "active", limit: 20 } } }),
      );
      setMatches(page.items);
    } catch (caught) {
      fail(caught);
    }
  };

  const book = (client: ClientListItem) =>
    run(`book-${client.id}`, async () => {
      const booking = unwrap(
        await api.POST("/sessions/{session_id}/bookings", {
          params: { ...scope, path: { session_id: id } },
          body: { client_id: client.id },
        }),
      );
      const name = [client.first_name, client.last_name].filter(Boolean).join(" ");
      setNotice(booking.status === "waitlisted" ? tSession("waitlisted", { name }) : tSession("booked", { name }));
      setAdding(false);
      setMatches(null);
      setSearch("");
    });

  const saveNote = (booking: Booking) =>
    run(`note-${booking.id}`, async () => {
      unwrap(
        await api.POST("/clients/{client_id}/notes", {
          params: { ...scope, path: { client_id: booking.client_id } },
          body: { body: note, booking_id: booking.id },
        }),
      );
      setNotice(tSession("noteSaved", { name: booking.client_name }));
      setNoteFor(null);
      setNote("");
    });

  if (!data) {
    return (
      <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
        <BackBar label={t("backToDay")} palette={palette} onPress={() => router.back()} />
      </Screen>
    );
  }
  const { session, bookings } = data;
  const coming = bookings.filter((b) => b.status !== "cancelled");
  const bookedIds = new Set(coming.map((b) => b.client_id));
  const isClass = session.booking_mode === "class";
  const open = session.status !== "cancelled";

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <BackBar label={t("backToDay")} palette={palette} onPress={() => router.back()} />
      <View style={{ gap: 6 }}>
        <Heading palette={palette}>{session.service.name}</Heading>
        <Text style={[styles.muted, { color: palette.muted }]}>
          {formatDay(dayOf(session.starts_at, timeZone), locale, { weekday: "long", day: "numeric", month: "long" })} ·{" "}
          {formatTime(session.starts_at, locale, timeZone)}–{formatTime(session.ends_at, locale, timeZone)}
        </Text>
        <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
          {open ? (
            <Badge
              label={t("spots", { booked: session.booked, capacity: session.capacity })}
              tone={session.booked >= session.capacity ? "primary" : "muted"}
              palette={palette}
            />
          ) : (
            <Badge label={t("cancelled")} tone="danger" palette={palette} />
          )}
          {session.waitlisted > 0 && <Badge label={t("waitlist", { count: session.waitlisted })} palette={palette} />}
          {session.location_name && <Badge label={session.location_name} palette={palette} />}
        </View>
      </View>

      <View accessibilityLiveRegion="polite">
        {notice && <Text style={{ color: palette.success, fontWeight: "600" }}>{notice}</Text>}
        <ErrorText message={error} palette={palette} />
      </View>

      {manage && open && isClass && (
        <Card palette={palette}>
          {!adding ? (
            <Button label={tSession("book")} palette={palette} onPress={() => setAdding(true)} />
          ) : (
            <View style={{ gap: 10 }}>
              <Field
                label={tBookings("searchLabel")}
                placeholder={tBookings("searchPlaceholder")}
                palette={palette}
                value={search}
                onChangeText={setSearch}
                onSubmitEditing={() => void find()}
                returnKeyType="search"
                autoFocus
              />
              <View style={{ flexDirection: "row", gap: 8 }}>
                <View style={{ flex: 1 }}>
                  <Button label={tBookings("search")} palette={palette} onPress={() => void find()} />
                </View>
                <View style={{ flex: 1 }}>
                  <Button
                    label={tSession("close")}
                    variant="secondary"
                    palette={palette}
                    onPress={() => {
                      setAdding(false);
                      setMatches(null);
                    }}
                  />
                </View>
              </View>
              {matches !== null &&
                (matches.filter((c) => !bookedIds.has(c.id)).length === 0 ? (
                  <Text style={[styles.muted, { color: palette.muted }]}>{tBookings("noMatches")}</Text>
                ) : (
                  matches
                    .filter((c) => !bookedIds.has(c.id))
                    .map((client) => {
                      const name = [client.first_name, client.last_name].filter(Boolean).join(" ");
                      return (
                        <ListRow
                          key={client.id}
                          palette={palette}
                          leading={<Avatar name={name} palette={palette} size={36} />}
                          title={name}
                          subtitle={client.plan_name ?? tBookings("noPlan")}
                          accessibilityLabel={`${tBookings("book")}: ${name}`}
                          onPress={() => void book(client)}
                          trailing={busy === `book-${client.id}` ? <Text style={{ color: palette.muted }}>…</Text> : undefined}
                        />
                      );
                    })
                ))}
            </View>
          )}
        </Card>
      )}

      <SectionTitle title={t("roster")} palette={palette} />
      {coming.length === 0 ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("empty")}</Text>
        </Card>
      ) : (
        coming.map((booking) => {
          const tone = TONE[booking.status as keyof typeof TONE] ?? "muted";
          const writing = noteFor?.id === booking.id;
          return (
            <Card key={booking.id} palette={palette}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
                <Avatar name={booking.client_name} palette={palette} />
                <View style={{ flex: 1, gap: 4 }}>
                  <Text
                    accessibilityRole="link"
                    onPress={() => router.push(`/client/${booking.client_id}`)}
                    style={{ color: palette.foreground, fontWeight: "700", fontSize: 16 }}
                  >
                    {booking.client_name}
                  </Text>
                  <Text style={{ color: palette.muted, fontSize: 13 }}>{booking.plan_name ?? tBookings("noPlan")}</Text>
                </View>
                <Badge label={t(`statuses.${booking.status}`)} tone={tone} palette={palette} />
              </View>
              {manage && (
                <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
                  {open && (booking.status === "booked" || booking.status === "waitlisted") ? (
                    <>
                      {booking.status === "booked" && (
                        <View style={{ flexGrow: 1, flexBasis: "45%" }}>
                          <Button
                            label={t("checkIn")}
                            accessibilityLabel={`${t("checkIn")}: ${booking.client_name}`}
                            palette={palette}
                            busy={busy === booking.id}
                            onPress={() => void setStatus(booking, "checked_in")}
                          />
                        </View>
                      )}
                      {booking.status === "booked" && (
                        <View style={{ flexGrow: 1, flexBasis: "45%" }}>
                          <Button
                            label={t("noShow")}
                            accessibilityLabel={`${t("noShow")}: ${booking.client_name}`}
                            variant="secondary"
                            palette={palette}
                            busy={busy === booking.id}
                            onPress={() => void setStatus(booking, "no_show")}
                          />
                        </View>
                      )}
                      <View style={{ flexGrow: 1, flexBasis: "45%" }}>
                        <Button
                          label={tSession("note")}
                          accessibilityLabel={tSession("noteFor", { name: booking.client_name })}
                          variant="secondary"
                          palette={palette}
                          onPress={() => {
                            setNoteFor(writing ? null : booking);
                            setNote("");
                          }}
                        />
                      </View>
                      <View style={{ flexGrow: 1, flexBasis: "45%" }}>
                        <Button
                          label={tSession("cancel")}
                          accessibilityLabel={`${tSession("cancel")}: ${booking.client_name}`}
                          variant="danger"
                          palette={palette}
                          onPress={() => void cancel(booking)}
                        />
                      </View>
                    </>
                  ) : (
                    <>
                      {open && (
                        <View style={{ flexGrow: 1, flexBasis: "45%" }}>
                          <Button
                            label={t("undo")}
                            accessibilityLabel={`${t("undo")}: ${booking.client_name}`}
                            variant="secondary"
                            palette={palette}
                            busy={busy === booking.id}
                            onPress={() => void setStatus(booking, "booked")}
                          />
                        </View>
                      )}
                      <View style={{ flexGrow: 1, flexBasis: "45%" }}>
                        <Button
                          label={tSession("note")}
                          accessibilityLabel={tSession("noteFor", { name: booking.client_name })}
                          variant="secondary"
                          palette={palette}
                          onPress={() => {
                            setNoteFor(writing ? null : booking);
                            setNote("");
                          }}
                        />
                      </View>
                    </>
                  )}
                </View>
              )}
              {writing && (
                <View style={{ gap: 8 }}>
                  <Field
                    label={tSession("noteFor", { name: booking.client_name })}
                    placeholder={tNotes("body")}
                    palette={palette}
                    value={note}
                    onChangeText={setNote}
                    multiline
                    style={{ minHeight: 88, paddingTop: 12, textAlignVertical: "top" }}
                  />
                  <Button
                    label={tNotes("add")}
                    palette={palette}
                    busy={busy === `note-${booking.id}`}
                    disabled={!note.trim()}
                    onPress={() => void saveNote(booking)}
                  />
                </View>
              )}
            </Card>
          );
        })
      )}
    </Screen>
  );
}
