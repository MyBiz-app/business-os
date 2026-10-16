import { StyleSheet, View } from "react-native";
import { useTranslations } from "use-intl";

import { Text } from "@business-os/app-kit/components/text";
import type { Palette } from "@business-os/app-kit/lib/theme";
import { InstructorAvatar } from "@/components/instructor-avatar";
import { type Person, personName } from "@/lib/friends";

const SHOWN = 4;
const SIZE = 24;

type Props = { people: Person[]; booked: number; capacity: number; palette: Palette };

/** "8/10" with a row of small, overlapping pictures of who is coming ("+3" when there are more). */
export function AttendeeStack({ people, booked, capacity, palette }: Props) {
  const t = useTranslations("friends");
  const shown = people.slice(0, SHOWN);
  const more = Math.max(booked - shown.length, 0);
  return (
    <View style={styles.row} accessible accessibilityLabel={t("spotsFilled", { booked, capacity })}>
      <Text style={[styles.count, { color: palette.foreground }]}>{t("spotsFilled", { booked, capacity })}</Text>
      {shown.length > 0 && (
        <View style={styles.stack}>
          {shown.map((person, index) => (
            <View
              key={person.client_id}
              style={[styles.ring, { borderColor: palette.surface, marginStart: index === 0 ? 0 : -8 }]}
            >
              <InstructorAvatar name={personName(person)} path={person.avatar_url} palette={palette} size={SIZE} />
            </View>
          ))}
          {more > 0 && (
            <Text style={[styles.more, { color: palette.muted }]} aria-hidden>
              +{more}
            </Text>
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 4 },
  count: { fontSize: 14, fontWeight: "600", fontVariant: ["tabular-nums"], textAlign: "left" },
  stack: { flexDirection: "row", alignItems: "center" },
  ring: { borderWidth: 2, borderRadius: SIZE, overflow: "hidden" },
  more: { fontSize: 13, fontWeight: "600", marginStart: 6 },
});
