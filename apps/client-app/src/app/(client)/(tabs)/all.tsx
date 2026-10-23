import { localValue, formatTime, todayIn } from "@business-os/i18n/dates";
import { router, type Href } from "expo-router";
import { Image, Linking, StyleSheet, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Text } from "@business-os/app-kit/components/text";
import { Avatar, Badge, ListRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Card, Heading, LoadError, Screen, SkeletonCard, styles } from "@business-os/app-kit/components/ui";
import { rebookTarget } from "@business-os/app-kit/lib/all-mine";
import { assetUrl } from "@business-os/app-kit/lib/api";
import { WEB_URL } from "@business-os/app-kit/lib/env";
import { radius } from "@business-os/app-kit/lib/theme";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";
import { BusinessStrip } from "@/components/business-strip";
import { useOpenBusiness } from "@/lib/use-open-business";
import { useOverview, type ClientOverview } from "@/lib/use-overview";
import { type ClientBusiness, useBusiness } from "@/providers/business-provider";

type Waiting = ClientOverview["waiting"][number];
type Rebook = ClientOverview["rebook"][number];

const DAY_MS = 86_400_000;

/** "All mine": what is next, the cards and what waits for the person, across every business they
 * are a client of. Drawn in MyBiz's own look, not a business's, so it is always clear that this is
 * the whole picture and not one business. */
export default function AllMine() {
  const t = useTranslations("client.all");
  const locale = useLocale();
  const { palette } = useTheme();
  const { businesses } = useBusiness();
  const open = useOpenBusiness();
  const { data, error, loading, reload } = useOverview(true);
  const byId = new Map((businesses ?? []).map((b) => [b.id, b]));

  const zone = (id: string) => byId.get(id)?.time_zone ?? "UTC";
  const name = (id: string) => byId.get(id)?.name ?? "";
  const when = (id: string, iso: string) =>
    `${new Intl.DateTimeFormat(locale, { weekday: "short", day: "numeric", month: "short", timeZone: zone(id) }).format(new Date(iso))} ${formatTime(iso, locale, zone(id))}`;
  const date = (day: string) => new Intl.DateTimeFormat(locale, { day: "numeric", month: "long", timeZone: "UTC" }).format(new Date(`${day}T12:00:00Z`));
  const daysLeft = (id: string, day: string) =>
    Math.round((Date.parse(`${day}T12:00:00Z`) - Date.parse(`${todayIn(zone(id))}T12:00:00Z`)) / DAY_MS);

  const waitingTitle = (w: Waiting) => t(w.kind, { name: w.title ?? "" });
  const openWaiting = (w: Waiting) => {
    if ((w.kind === "payment" || w.kind === "quote") && w.ref) {
      void Linking.openURL(`${WEB_URL}/q/${w.ref}`);
      return;
    }
    const target: Href =
      w.kind === "health" ? "/health" : w.kind === "document" ? "/documents" : w.kind === "review" && w.ref
        ? { pathname: "/review/[id]", params: { id: w.ref, service: w.title ?? "" } }
        : "/bookings";
    void open(w.business_id, target);
  };

  const openRebook = (r: Rebook) => {
    const base = { service: r.service_id };
    const params =
      r.booking_mode === "resource"
        ? { ...base, at: localValue(r.last_at, zone(r.business_id)).slice(11, 16) }
        : r.booking_mode === "appointment"
          ? { ...base, ...(r.instructor_user_id ? { staff: r.instructor_user_id } : {}) }
          : base;
    void open(r.business_id, { pathname: rebookTarget(r.booking_mode), params } as Href);
  };

  const dormant = (data?.businesses ?? []).filter((b) => b.dormant);

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <Heading palette={palette}>{t("title")}</Heading>
      <BusinessStrip palette={palette} overview={data} />

      {error !== undefined && !data && <LoadError palette={palette} onRetry={() => void reload()} />}
      {!data && error === undefined && <SkeletonCard palette={palette} label={t("title")} />}

      {data && (
        <>
          <View style={local.section}>
            <SectionTitle title={t("next")} palette={palette} />
            {data.next.length === 0 && <Text style={[styles.muted, { color: palette.muted }]}>{t("nextEmpty")}</Text>}
            {data.next.map((visit) => (
              <ListRow
                key={visit.booking_id}
                palette={palette}
                leading={<Mark business={byId.get(visit.business_id)} palette={palette} />}
                title={visit.service_name}
                subtitle={[
                  `${when(visit.business_id, visit.starts_at)} · ${name(visit.business_id)}`,
                  visit.room_name ?? visit.instructor_name,
                  visit.friends.length > 0 ? t("withFriends", { names: visit.friends.join(", ") }) : null,
                ]
                  .filter(Boolean)
                  .join("\n")}
                trailing={visit.status === "waitlisted" ? <Badge label={t("waitlisted")} palette={palette} /> : null}
                onPress={() => void open(visit.business_id, "/bookings")}
              />
            ))}
          </View>

          <View style={local.section}>
            <SectionTitle title={t("cards")} palette={palette} />
            {data.cards.length === 0 && <Text style={[styles.muted, { color: palette.muted }]}>{t("cardsEmpty")}</Text>}
            {data.cards.map((card) => {
              const left = daysLeft(card.business_id, card.ends_on);
              const ends = left < 0 ? "" : left === 0 ? t("endsToday") : left <= 14 ? t("endsSoon", { days: left }) : t("endsOn", { date: date(card.ends_on) });
              return (
                <ListRow
                  key={card.entitlement_id}
                  palette={palette}
                  leading={<Mark business={byId.get(card.business_id)} palette={palette} />}
                  title={card.name}
                  subtitle={[name(card.business_id), card.credits_remaining != null ? t("creditsLeft", { count: card.credits_remaining }) : null, ends]
                    .filter(Boolean)
                    .join(" · ")}
                  trailing={left >= 0 && left <= 14 ? <Badge label={ends} tone="danger" palette={palette} /> : null}
                  onPress={() => void open(card.business_id, "/home")}
                />
              );
            })}
          </View>

          <View style={local.section}>
            <SectionTitle title={t("waiting")} palette={palette} />
            {data.waiting.length === 0 && <Text style={[styles.muted, { color: palette.muted }]}>{t("waitingEmpty")}</Text>}
            {data.waiting.map((w, index) => (
              <ListRow
                key={`${w.business_id}-${w.kind}-${w.ref ?? index}`}
                palette={palette}
                leading={<Mark business={byId.get(w.business_id)} palette={palette} />}
                title={waitingTitle(w)}
                subtitle={name(w.business_id)}
                onPress={() => openWaiting(w)}
              />
            ))}
          </View>

          {data.rebook.length > 0 && (
            <View style={local.section}>
              <SectionTitle title={t("rebook")} palette={palette} />
              {data.rebook.map((r) => (
                <ListRow
                  key={`${r.business_id}-${r.service_id}-${r.room_id ?? ""}-${r.instructor_user_id ?? ""}`}
                  palette={palette}
                  leading={<Mark business={byId.get(r.business_id)} palette={palette} />}
                  title={r.service_name}
                  subtitle={[name(r.business_id), r.room_name, r.instructor_name].filter(Boolean).join(" · ")}
                  trailing={<Badge label={t("rebookAction")} tone="primary" palette={palette} />}
                  onPress={() => openRebook(r)}
                />
              ))}
            </View>
          )}

          {dormant.map(({ business }) => (
            <Card key={business.id} palette={palette}>
              <Text accessibilityRole="header" style={[local.dormantTitle, { color: palette.foreground }]}>
                {t("dormant")}
              </Text>
              <Text style={[styles.muted, { color: palette.muted }]}>{t("dormantHint", { name: business.name })}</Text>
              <ListRow
                palette={palette}
                title={business.name}
                leading={<Mark business={byId.get(business.id)} palette={palette} />}
                trailing={<Badge label={t("dormantAction")} tone="primary" palette={palette} />}
                accessibilityLabel={t("openBusiness", { name: business.name })}
                onPress={() => void open(business.id, "/schedule")}
              />
            </Card>
          ))}
        </>
      )}
    </Screen>
  );
}

/** A business's logo (or its initials) on a row, so each line says where it comes from. */
function Mark({ business, palette }: { business?: ClientBusiness; palette: Parameters<typeof Avatar>[0]["palette"] }) {
  const logo = assetUrl(business?.logo_url);
  if (!business) return null;
  return logo ? (
    <Image source={{ uri: logo }} style={local.logo} accessibilityIgnoresInvertColors />
  ) : (
    <Avatar name={business.name} color={business.primary_color} palette={palette} size={40} />
  );
}

const local = StyleSheet.create({
  section: { gap: 8 },
  logo: { width: 40, height: 40, borderRadius: radius.pill },
  dormantTitle: { fontSize: 17, fontWeight: "600", textAlign: "left" },
});
