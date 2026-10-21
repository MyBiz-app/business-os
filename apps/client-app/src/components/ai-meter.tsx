import { View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useTranslations } from "use-intl";

import { styles } from "@business-os/app-kit/components/ui";
import type { Palette } from "@business-os/app-kit/lib/theme";

export type AiMeterData = {
  pace_percent: number;
  business: { percent: number; level: "ok" | "warn" | "over"; reach_date: string | null; questions_left: number | null } | null;
  person: { used_today: number; day_limit: number | null; questions_left_today: number | null; level: "ok" | "warn" | "over" };
};

/** How much of the month's AI is used, against the calendar: the mark is where an even pace would be
 * today. Managers see the business; everyone else sees their own allowance for today. */
export function AiMeter({ meter, palette }: { meter: AiMeterData; palette: Palette }) {
  const t = useTranslations("aiTeam.meter");
  const { business, person } = meter;
  const level = business ? business.level : person.level;
  const percent = business ? business.percent : person.day_limit ? (100 * person.used_today) / person.day_limit : 0;
  const shown = Math.min(100, Math.max(0, percent));
  const color = level === "over" ? palette.danger : level === "warn" ? palette.warning : palette.primary;
  const headline = business ? t("business", { percent: Math.round(business.percent) }) : t("person", { percent: Math.round(percent) });
  const detail = business
    ? business.reach_date
      ? t("reach", { date: business.reach_date.slice(8, 10) + "/" + business.reach_date.slice(5, 7) })
      : t("left", { count: business.questions_left ?? 0 })
    : person.questions_left_today !== null
      ? t("leftToday", { count: person.questions_left_today })
      : t("noPace");
  return (
    <View style={{ gap: 6 }} accessible accessibilityRole="progressbar" accessibilityLabel={`${headline}. ${detail}`} accessibilityValue={{ min: 0, max: 100, now: Math.round(shown) }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        <Text style={{ color: palette.foreground, fontWeight: "600" }}>{headline}</Text>
        <Text style={[styles.muted, { color: palette.muted }]}>{detail}</Text>
      </View>
      <View style={{ height: 10, borderRadius: 5, backgroundColor: palette.border }}>
        <View style={{ height: 10, borderRadius: 5, width: `${shown}%`, backgroundColor: color }} />
        {business && <View style={{ position: "absolute", top: -3, bottom: -3, width: 2, borderRadius: 1, start: `${meter.pace_percent}%`, backgroundColor: palette.foreground }} />}
      </View>
    </View>
  );
}
