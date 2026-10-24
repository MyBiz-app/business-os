import type { components } from "@business-os/api-client";
import { formatDay } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { Chip } from "@business-os/app-kit/components/chip";
import { PressableScale } from "@business-os/app-kit/components/motion";
import { EmptyState, styles } from "@business-os/app-kit/components/ui";
import { courtGrid, clockOf, staffRows } from "@/lib/availability";
import { rentalLengths } from "@/lib/court-search";
import { useBusiness } from "@/providers/business-provider";
import { radius } from "@business-os/app-kit/lib/theme";
import { Spinner } from "@business-os/app-kit/components/spinner";

type Court = components["schemas"]["ResourceService"];
type CourtSlot = components["schemas"]["ResourceSlot"];
type Visit = components["schemas"]["AppointmentService"];
type VisitSlot = components["schemas"]["Slot"];

/** What the schedule shows for a business that rents courts or takes appointments, for the days on screen. */
export function Availability({ kind, days, courts, visits }: { kind: "courts" | "appointments"; days: string[]; courts: Court[]; visits: Visit[] }) {
  const t = useTranslations("client.schedule");
  const { palette } = useBusiness();
  const options: { id: string; name: string }[] = kind === "courts" ? courts : visits;
  const [chosen, setChosen] = useState<string | null>(null);
  const pick = options.find((o) => o.id === chosen) ?? options[0];
  if (!pick) return null;
  return (
    <View style={local.block}>
      {options.length > 1 && (
        <ScrollView horizontal role="tablist" showsHorizontalScrollIndicator={false} contentContainerStyle={local.chips}>
          {options.map((o) => (
            <Chip key={o.id} role="tab" label={o.name} selected={o.id === pick.id} onPress={() => setChosen(o.id)} palette={palette} />
          ))}
        </ScrollView>
      )}
      {days.length === 0 && <EmptyState palette={palette} message={t("empty")} icon="calendar-outline" />}
      {days.map((day) => (
        <DayAvailability key={`${kind}-${pick.id}-${day}`} kind={kind} day={day} serviceId={pick.id} court={kind === "courts" ? (pick as Court) : null} />
      ))}
    </View>
  );
}

function DayAvailability({ kind, day, serviceId, court }: { kind: "courts" | "appointments"; day: string; serviceId: string; court: Court | null }) {
  const t = useTranslations("client.schedule");
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();
  const [slots, setSlots] = useState<(CourtSlot | VisitSlot)[] | null>(null);
  const zone = business?.time_zone ?? "UTC";
  const minutes = court ? (rentalLengths(court)[0] ?? court.min_minutes) : null;

  useEffect(() => {
    let stale = false;
    setSlots(null);
    const request =
      kind === "courts"
        ? api.GET("/client/resources/slots", { params: { ...scope, query: { service_id: serviceId, date: day, minutes: minutes ?? 60 } } })
        : api.GET("/client/appointments/slots", { params: { ...scope, query: { service_id: serviceId, date: day } } });
    void Promise.resolve(request)
      .then((result) => {
        if (!stale) setSlots((result.data as (CourtSlot | VisitSlot)[] | undefined) ?? []);
      })
      .catch(() => {
        if (!stale) setSlots([]);
      });
    return () => {
      stale = true;
    };
  }, [api, scope, kind, serviceId, day, minutes]);

  const open = (at: string) =>
    router.push({ pathname: kind === "courts" ? "/court" : "/appointment", params: { day, at, service: serviceId } });

  return (
    <View style={local.day}>
      <Text style={[local.head, { color: palette.foreground }]}>{formatDay(day, locale, { weekday: "long", day: "numeric", month: "long" })}</Text>
      {slots === null ? (
        <Spinner color={palette.primary} />
      ) : slots.length === 0 ? (
        <Text style={[styles.muted, { color: palette.muted }]}>{t("noFree")}</Text>
      ) : kind === "courts" ? (
        <CourtTable slots={slots as CourtSlot[]} zone={zone} onPick={open} />
      ) : (
        <StaffList slots={slots as VisitSlot[]} zone={zone} onPick={open} />
      )}
    </View>
  );
}

/** Courts down the side, start times across the top, a tappable cell where the court is free. */
function CourtTable({ slots, zone, onPick }: { slots: CourtSlot[]; zone: string; onPick: (at: string) => void }) {
  const { palette } = useBusiness();
  const grid = courtGrid(slots, zone);
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false}>
      <View style={local.table}>
        <View style={local.tableRow}>
          <View style={local.nameCell} />
          {grid.hours.map((h) => (
            <Text key={h} style={[local.hour, { color: palette.muted }]}>
              {h}
            </Text>
          ))}
        </View>
        {grid.courts.map((row) => (
          <View key={row.roomId} style={local.tableRow}>
            <Text numberOfLines={1} style={[local.nameCell, { color: palette.foreground }]}>
              {row.name}
            </Text>
            {grid.hours.map((h) => {
              const cell = row.cells[h];
              return cell ? (
                <PressableScale
                  key={h}
                  accessibilityRole="button"
                  accessibilityLabel={`${row.name} ${h}`}
                  onPress={() => onPick(h)}
                  style={[local.cell, { backgroundColor: palette.primary }]}
                >
                  <Text style={[local.cellText, { color: palette.onPrimary }]}>{h}</Text>
                </PressableScale>
              ) : (
                <View key={h} style={[local.cell, { backgroundColor: palette.surface, borderColor: palette.border, borderWidth: 1 }]} />
              );
            })}
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

/** One row per staff member with the times they are free. */
function StaffList({ slots, zone, onPick }: { slots: VisitSlot[]; zone: string; onPick: (at: string) => void }) {
  const { palette } = useBusiness();
  return (
    <View style={local.block}>
      {staffRows(slots).map((row) => (
        <View key={row.staffId} style={local.block}>
          <Text style={[local.staff, { color: palette.foreground }]}>{row.name}</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={local.chips}>
            {row.slots.map((s) => (
              <Chip key={s.starts_at} label={clockOf(s.starts_at, zone)} selected={false} onPress={() => onPick(clockOf(s.starts_at, zone))} palette={palette} />
            ))}
          </ScrollView>
        </View>
      ))}
    </View>
  );
}

const local = StyleSheet.create({
  block: { gap: 8 },
  chips: { gap: 8, paddingVertical: 2 },
  day: { gap: 8 },
  head: { fontSize: 15, fontWeight: "600", marginTop: 4 },
  staff: { fontSize: 13, fontWeight: "500" },
  table: { gap: 6 },
  tableRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  nameCell: { width: 84, fontSize: 13, fontWeight: "500" },
  hour: { width: 56, fontSize: 12, textAlign: "center" },
  cell: { width: 56, height: 36, borderRadius: radius.control, alignItems: "center", justifyContent: "center" },
  cellText: { fontSize: 12, fontWeight: "600" },
});
