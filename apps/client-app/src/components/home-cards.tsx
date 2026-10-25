import Ionicons from "@expo/vector-icons/Ionicons";
import type { components } from "@business-os/api-client";
import { formatTime } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useState, type ReactNode } from "react";
import { Image, Linking, StyleSheet, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { ActionPill } from "@business-os/app-kit/components/action-pill";
import { PressableScale } from "@business-os/app-kit/components/motion";
import { Badge, ListRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Text } from "@business-os/app-kit/components/text";
import { Card, EmptyState, styles } from "@business-os/app-kit/components/ui";
import { assetUrl } from "@business-os/app-kit/lib/api";
import { tint } from "@business-os/app-kit/lib/brand";
import { byDistance, distanceLabel, hasPoint } from "@business-os/app-kit/lib/distance";
import { lastVisit, nextBooking, type HomeCard } from "@business-os/app-kit/lib/client-home";
import { googleMapsLink, wazeLink } from "@business-os/app-kit/lib/maps";
import { bookingModesFor, useTerm } from "@business-os/app-kit/lib/vertical";
import { BookingActions } from "@/components/booking-actions";
import { BranchMap } from "@/components/branch-map";
import { addressOf, type Location } from "@/lib/use-locations";
import { notificationIcon, useNotificationText } from "@/lib/notification-text";
import { useAccount } from "@/lib/use-account";
import { useDevicePosition } from "@/lib/use-device-position";
import { useDependents } from "@/lib/use-dependents";
import { useHealth } from "@/lib/use-health";
import { useBusiness } from "@/providers/business-provider";
import { useInbox } from "@/providers/inbox-provider";
import { fixedColors, radius } from "@business-os/app-kit/lib/theme";

type Booking = components["schemas"]["ClientBooking"];
type Session = components["schemas"]["ClientSession"];
type Entitlement = components["schemas"]["Entitlement"];

/** What the home cards draw from, loaded once by the home screen. */
export type HomeData = {
  bookings: Booking[];
  sessions: Session[];
  entitlements: Entitlement[];
  /** Appointment services and rentable courts/rooms the client can book here. */
  appointments: number;
  courts: number;
  locations: Location[];
  reload: () => void;
};

const CURRENT = new Set<Entitlement["state"]>(["active", "upcoming", "frozen"]);

/** One home card: a title row with an optional "see all", then its content. */
function Section({ title, action, onAction, children }: { title: string; action?: string; onAction?: () => void; children: ReactNode }) {
  const { palette } = useBusiness();
  return (
    <View style={local.section}>
      <SectionTitle title={title} action={action} onAction={onAction} palette={palette} />
      {children}
    </View>
  );
}

function NextBooking({ data }: { data: HomeData }) {
  const t = useTranslations("client.homeCards");
  const term = useTerm();
  const locale = useLocale();
  const { business, palette } = useBusiness();
  if (!business) return null;
  const next = nextBooking(data.bookings, Date.now());
  const book = () => router.navigate(data.appointments > 0 ? "/appointment" : data.courts > 0 ? "/court" : "/schedule");
  return (
    <Section title={term(business, "nextBooking")}>
      {next ? (
        <NextBookingBody booking={next} data={data} locale={locale} />
      ) : (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("nothingBooked")}</Text>
          <ActionPill label={t("bookNow")} icon="add-circle-outline" palette={palette} onPress={book} />
        </Card>
      )}
    </Section>
  );
}

function NextBookingBody({ booking, data, locale }: { booking: Booking; data: HomeData; locale: string }) {
  const { business, palette } = useBusiness();
  if (!business) return null;
  const session = data.sessions.find((s) => s.id === booking.session_id);
  const address = addressOf(data.locations, session?.location_name);
  const color = session?.service.color ?? palette.primary;
  const day = new Intl.DateTimeFormat(locale, { weekday: "long", day: "numeric", month: "long", timeZone: business.time_zone });
  const place = [session?.location_name, session?.room_name].filter(Boolean).join(" · ");
  return (
    <View style={[local.next, { backgroundColor: palette.surface, borderColor: palette.border }]}>
      <View aria-hidden style={[local.orb, { backgroundColor: tint(color, 0.14) }]} />
      <View style={local.nextHead}>
        <View style={[local.nextAccent, { backgroundColor: color }]} />
        <View style={local.grow}>
          <Text style={[local.nextTitle, { color: palette.foreground }]}>{booking.service_name}</Text>
          <Text style={[local.nextMeta, { color: palette.muted }]}>
            {day.format(new Date(booking.starts_at))} · {formatTime(booking.starts_at, locale, business.time_zone)}
          </Text>
          {place ? <Text style={[local.nextMeta, { color: palette.muted }]}>{place}</Text> : null}
          {booking.dependent_name ? <Text style={[local.nextMeta, { color: palette.muted }]}>{booking.dependent_name}</Text> : null}
        </View>
      </View>
      <BookingActions booking={booking} address={address} onChange={data.reload} />
    </View>
  );
}

/** The membership as a Wallet-style card in the business's color: name, entries left or validity,
 * and the business on it. Several current plans stack as smaller lines under the first. */
function Membership({ data }: { data: HomeData }) {
  const t = useTranslations("client.homeCards");
  const tBookings = useTranslations("client.bookings");
  const tPlans = useTranslations("plans");
  const locale = useLocale();
  const { business, palette } = useBusiness();
  const current = data.entitlements.filter((e) => CURRENT.has(e.state));
  const day = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", timeZone: "UTC" });
  if (!business) return null;
  const main = current[0];
  if (!main) {
    return (
      <Section title={t("membership")}>
        <ListRow palette={palette} title={t("noPlan")} subtitle={t("noPlanHint")} onPress={() => router.navigate("/bookings")} />
      </Section>
    );
  }
  const kindLabel = (e: Entitlement) =>
    e.state !== "active" ? tPlans(`states.${e.state}`) : e.credits_remaining === null ? tPlans("kinds.membership") : null;
  const logo = assetUrl(business.logo_url);
  return (
    <Section title={t("membership")} action={tBookings("title")} onAction={() => router.navigate("/bookings")}>
      <PressableScale
        accessibilityRole="button"
        accessibilityLabel={`${main.name}, ${kindLabel(main) ?? tBookings("entriesLeft", { count: main.credits_remaining ?? 0 })}`}
        onPress={() => router.navigate("/bookings")}
        style={[local.wallet, { backgroundColor: palette.primary }]}
      >
        <View aria-hidden style={[local.orb, { backgroundColor: tint(palette.onPrimary, 0.12) }]} />
        <View style={local.walletTop}>
          <Text style={[local.walletName, { color: palette.onPrimary }]} numberOfLines={2}>{main.name}</Text>
          {logo && <Image source={{ uri: logo }} style={local.walletLogo} accessibilityIgnoresInvertColors />}
        </View>
        <View>
          {kindLabel(main) ? (
            <Text style={[local.walletBig, { color: palette.onPrimary }]}>{kindLabel(main)}</Text>
          ) : (
            <Text style={[local.walletBig, { color: palette.onPrimary }]}>{main.credits_remaining}</Text>
          )}
          {main.credits_remaining !== null && main.state === "active" && (
            <Text style={[local.walletMeta, { color: palette.onPrimary }]}>{tBookings("entriesLeftLabel")}</Text>
          )}
          <Text style={[local.walletMeta, { color: palette.onPrimary }]}>
            {tBookings("validUntil", { date: day.format(new Date(`${main.ends_on}T12:00:00Z`)) })}
          </Text>
        </View>
      </PressableScale>
      {current.slice(1, 3).map((e) => (
        <View key={e.id} style={local.line}>
          <Text style={[local.lineTitle, { color: palette.foreground }]}>{e.name}</Text>
          <Text style={[local.lineMeta, { color: palette.muted }]}>
            {kindLabel(e) ?? tBookings("entriesLeft", { count: e.credits_remaining ?? 0 })} · {tBookings("validUntil", { date: day.format(new Date(`${e.ends_on}T12:00:00Z`)) })}
          </Text>
        </View>
      ))}
    </Section>
  );
}

function Shortcuts({ data }: { data: HomeData }) {
  const t = useTranslations("client.homeCards");
  const tAppointment = useTranslations("client.appointment");
  const tCourt = useTranslations("client.court");
  const term = useTerm();
  const { business, palette } = useBusiness();
  if (!business) return null;
  const items: { key: string; icon: "calendar-outline" | "cut-outline" | "tennisball-outline"; label: string; go: () => void }[] = [];
  if (bookingModesFor(business).includes("class") || data.sessions.length > 0 || data.appointments + data.courts === 0) {
    items.push({ key: "class", icon: "calendar-outline", label: term(business, "appTab"), go: () => router.navigate("/schedule") });
  }
  if (data.appointments > 0) items.push({ key: "appointment", icon: "cut-outline", label: tAppointment("cta"), go: () => router.push("/appointment") });
  if (data.courts > 0) items.push({ key: "court", icon: "tennisball-outline", label: tCourt("cta"), go: () => router.push("/court") });
  return (
    <Section title={t("bookTitle")}>
      <View style={local.tiles}>
        {items.map((item) => (
          <ListTile key={item.key} icon={item.icon} label={item.label} onPress={item.go} />
        ))}
      </View>
    </Section>
  );
}

function ListTile({ icon, label, onPress }: { icon: React.ComponentProps<typeof Ionicons>["name"]; label: string; onPress: () => void }) {
  const { palette } = useBusiness();
  return (
    <View style={local.tileBox}>
      <ListRow
        palette={palette}
        title={label}
        onPress={onPress}
        leading={
          <View style={[local.tileIcon, { backgroundColor: tint(palette.primary, 0.14) }]}>
            <Ionicons name={icon} size={20} color={palette.primary} />
          </View>
        }
      />
    </View>
  );
}

function Rebook({ data }: { data: HomeData }) {
  const t = useTranslations("client.homeCards");
  const locale = useLocale();
  const { business, palette } = useBusiness();
  const last = lastVisit(data.bookings, Date.now());
  if (!business || !last) return null;
  const date = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", timeZone: business.time_zone });
  const go = () => router.navigate(data.appointments > 0 ? "/appointment" : data.courts > 0 ? "/court" : "/schedule");
  return (
    <Section title={t("rebook")}>
      <ListRow
        palette={palette}
        title={t("rebookTitle", { service: last.service_name })}
        subtitle={t("rebookHint", { date: date.format(new Date(last.starts_at)) })}
        onPress={go}
        leading={<Ionicons name="repeat-outline" size={22} color={palette.primary} />}
      />
    </Section>
  );
}

function Dependents() {
  const t = useTranslations("client.homeCards");
  const tDependents = useTranslations("dependents");
  const dependents = useDependents();
  const { business, palette } = useBusiness();
  if (!business?.dependents) return null;
  const kind = business.dependents;
  return (
    <Section title={tDependents(`title.${kind}`)} action={t("manage")} onAction={() => router.push("/dependents")}>
      <Card palette={palette}>
        {dependents.length === 0 ? (
          <Text style={[styles.muted, { color: palette.muted }]}>{tDependents(`none.${kind}`)}</Text>
        ) : (
          <View style={local.chips}>
            {dependents.map((d) => (
              <Badge key={d.id} label={d.name} tone="primary" palette={palette} />
            ))}
          </View>
        )}
        <ActionPill label={tDependents(`add.${kind}`)} icon="add-circle-outline" palette={palette} onPress={() => router.push("/dependents")} />
      </Card>
    </Section>
  );
}

function Health() {
  const t = useTranslations("client.homeCards");
  const tHealth = useTranslations("client.health");
  const locale = useLocale();
  const health = useHealth();
  const { palette } = useBusiness();
  if (!health?.required) return null;
  const until = health.current
    ? new Intl.DateTimeFormat(locale, { dateStyle: "long", timeZone: "UTC" }).format(new Date(`${health.current.valid_until}T12:00:00Z`))
    : null;
  return (
    <Section title={t("health")}>
      <ListRow
        palette={palette}
        title={health.state === "ok" ? t("healthOk") : tHealth("banner")}
        subtitle={health.state === "ok" && until ? t("healthUntil", { date: until }) : undefined}
        onPress={() => router.push("/health")}
        leading={<Ionicons name={health.state === "ok" ? "shield-checkmark-outline" : "alert-circle-outline"} size={22} color={palette.primary} />}
      />
    </Section>
  );
}

/** A link row for something the client keeps in their account (documents, quotes, addresses). */
function AccountLink({ title, subtitle, icon, to }: { title: string; subtitle?: string; icon: React.ComponentProps<typeof Ionicons>["name"]; to: "/documents" | "/quotes" | "/addresses" }) {
  const { palette } = useBusiness();
  return (
    <ListRow palette={palette} title={title} subtitle={subtitle} onPress={() => router.push(to)} leading={<Ionicons name={icon} size={22} color={palette.primary} />} />
  );
}

function Documents() {
  const t = useTranslations("client.homeCards");
  const account = useAccount();
  return <AccountLink title={t("documents")} subtitle={t("documentsCount", { count: account.documents.length })} icon="document-text-outline" to="/documents" />;
}

function Quotes() {
  const t = useTranslations("client.homeCards");
  const account = useAccount();
  return <AccountLink title={t("quotes")} subtitle={t("quotesCount", { count: account.quotes.length })} icon="receipt-outline" to="/quotes" />;
}

function Addresses() {
  const t = useTranslations("client.homeCards");
  const account = useAccount();
  if (!account.onSite) return null;
  return <AccountLink title={t("addresses")} subtitle={t("addressesHint")} icon="home-outline" to="/addresses" />;
}

function Updates() {
  const t = useTranslations("client.homeCards");
  const text = useNotificationText();
  const { inbox } = useInbox();
  const { palette } = useBusiness();
  const items = (inbox?.items ?? []).slice(0, 3);
  return (
    <Section title={t("updates")} action={items.length > 0 ? t("seeAll") : undefined} onAction={() => router.navigate("/updates")}>
      {items.length === 0 ? (
        <EmptyState palette={palette} message={t("noUpdates")} />
      ) : (
        <Card palette={palette}>
          {items.map((n, index) => (
            <View key={n.id} style={[local.line, index > 0 && { borderTopWidth: 1, borderTopColor: palette.border }]}>
              <Ionicons name={notificationIcon(n.kind)} size={20} color={n.read_at ? palette.muted : palette.primary} />
              <Text style={[local.lineTitle, local.grow, { color: palette.foreground }]} numberOfLines={2}>
                {text(n)}
              </Text>
            </View>
          ))}
        </Card>
      )}
    </Section>
  );
}

/** Our branches: the map, distances and navigation. Lives in the Profile tab. */
export function BusinessInfo({ data }: { data: Pick<HomeData, "locations"> }) {
  const t = useTranslations("client.homeCards");
  const { business, palette } = useBusiness();
  const [selected, setSelected] = useState<string>();
  const device = useDevicePosition();
  if (!business) return null;
  const placed = data.locations.filter(hasPoint);
  // Nearest first once the person shared where they are; the position never leaves this phone.
  const ranked = device.position ? byDistance(device.position, data.locations) : [];
  const km = new Map(ranked.map((r) => [r.place.id, r.km]));
  const locations = device.position ? [...data.locations].sort((a, b) => (km.get(a.id) ?? Infinity) - (km.get(b.id) ?? Infinity)) : data.locations;
  const nearest = ranked[0]?.place.id;
  const near = () => {
    void device.request();
  };
  return (
    <Section title={t("businessInfo")}>
      <Card palette={palette}>
        <Text style={[local.lineTitle, { color: palette.foreground }]}>{business.name}</Text>
        <BranchMap locations={data.locations} selectedId={selected ?? nearest} onSelect={setSelected} />
        {placed.length > 1 && device.state !== "ready" ? (
          <View style={local.chips}>
            <ActionPill label={t("nearMe")} icon="locate-outline" palette={palette} busy={device.state === "asking"} onPress={near} />
          </View>
        ) : null}
        {device.state === "denied" || device.state === "unavailable" ? (
          <Text style={[local.lineMeta, { color: palette.muted }]}>{t(device.state === "denied" ? "nearMeDenied" : "nearMeUnavailable")}</Text>
        ) : null}
        {locations.map((location) => {
          const away = km.get(location.id);
          const label = away == null ? null : distanceLabel(away);
          return (
            <View key={location.id} style={local.line}>
              <View style={local.grow}>
                {data.locations.length > 1 && <Text style={[local.lineTitle, { color: palette.foreground }]}>{location.name}</Text>}
                <Text style={[local.lineMeta, { color: palette.muted }]}>{location.address ?? t("noAddress")}</Text>
                {label ? (
                  <Text style={[local.lineMeta, { color: location.id === nearest ? palette.primary : palette.muted }]}>
                    {t(location.id === nearest ? "nearestAway" : "away", { distance: t(label.unit === "m" ? "meters" : "kilometers", { value: label.value }) })}
                  </Text>
                ) : null}
              </View>
              <View style={local.chips}>
                {location.address ? (
                  <>
                    <ActionPill label={t("navigateWaze")} icon="navigate-outline" palette={palette} onPress={() => void Linking.openURL(wazeLink(location.address!, location))} />
                    <ActionPill label={t("navigateGoogle")} icon="map-outline" palette={palette} onPress={() => void Linking.openURL(googleMapsLink(location.address!, location))} />
                  </>
                ) : null}
                {location.website_url ? (
                  <ActionPill label={t("website")} icon="globe-outline" palette={palette} onPress={() => void Linking.openURL(location.website_url!)} />
                ) : null}
              </View>
            </View>
          );
        })}
      </Card>
    </Section>
  );
}

/** The cards a home can list (the industry catalog's `client_home`), keyed by name. A card with
 * nothing to show for this client draws nothing. */
export const HOME_CARDS: Record<HomeCard, (props: { data: HomeData }) => ReactNode> = {
  next_booking: NextBooking,
  membership: Membership,
  shortcuts: Shortcuts,
  rebook: Rebook,
  dependents: Dependents,
  health: Health,
  documents: Documents,
  quotes: Quotes,
  addresses: Addresses,
  updates: Updates,
  business_info: BusinessInfo,
};

const local = StyleSheet.create({
  section: { gap: 8 },
  grow: { gap: 2 },
  // One branch per block: name, address and distance at full width, the navigation pills on their own row below.
  line: { gap: 8, paddingVertical: 8 },
  lineTitle: { fontSize: 15, fontWeight: "500", textAlign: "left" },
  lineMeta: { fontSize: 13, textAlign: "left" },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  tiles: { gap: 8 },
  tileBox: { width: "100%" },
  tileIcon: { width: 36, height: 36, borderRadius: radius.card, alignItems: "center", justifyContent: "center" },
  next: { borderWidth: 1, borderRadius: radius.card, padding: 18, gap: 14, overflow: "hidden" },
  orb: { position: "absolute", width: 180, height: 180, borderRadius: radius.pill, top: -80, end: -50 },
  nextHead: { flexDirection: "row", gap: 12 },
  nextAccent: { width: 5, borderRadius: 3 },
  nextTitle: { fontSize: 20, fontWeight: "600", textAlign: "left" },
  wallet: { borderRadius: radius.dialog, padding: 20, minHeight: 168, justifyContent: "space-between", overflow: "hidden" },
  walletTop: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: 12 },
  walletName: { flex: 1, fontSize: 20, fontWeight: "600", textAlign: "left" },
  walletLogo: { width: 40, height: 40, borderRadius: radius.card, backgroundColor: fixedColors.white },
  walletBig: { fontSize: 30, fontWeight: "600", textAlign: "left" },
  walletMeta: { fontSize: 13, opacity: 0.9, textAlign: "left" },
  nextMeta: { fontSize: 15, textAlign: "left" },
});
