import type { components } from "@business-os/api-client";
import Ionicons from "@expo/vector-icons/Ionicons";
import { router } from "expo-router";
import { formatDay } from "@business-os/i18n/dates";
import { useState } from "react";
import { Pressable, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Badge, ListRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Text } from "@business-os/app-kit/components/text";
import { Card, styles } from "@business-os/app-kit/components/ui";
import { font } from "@business-os/app-kit/lib/typography";
import type { Palette } from "@business-os/app-kit/lib/theme";

type AttentionList = components["schemas"]["AttentionList"];
type Kind = AttentionList["kind"];
type IconName = React.ComponentProps<typeof Ionicons>["name"];
type Tone = "success" | "danger" | "muted" | "primary";

/** Rows shown before "Show all", as on the web. */
const VISIBLE = 5;

/** Each list's icon, tone and place by urgency (lower is first): the same order as the web "Needs you". */
const KINDS: Record<Kind, { icon: IconName; tone: Tone; rank: number }> = {
  license_expiring: { icon: "ribbon-outline", tone: "danger", rank: 1 },
  freeze_requests: { icon: "snow-outline", tone: "danger", rank: 3 },
  health_review: { icon: "heart-outline", tone: "danger", rank: 4 },
  leads_due: { icon: "call-outline", tone: "primary", rank: 5 },
  plan_ending: { icon: "calendar-clear-outline", tone: "primary", rank: 6 },
  inactive: { icon: "person-remove-outline", tone: "muted", rank: 7 },
};

type Item = { id: string; name: string; subtitle?: string; open: () => void };
type Row = { key: string; rank: number; icon: IconName; tone: Tone; title: string; detail?: string; count?: number; items?: Item[]; open?: () => void };

/** Everything that needs the owner today in ONE list, most urgent first: usage warnings, then the
 * attention lists (licence, requests, who to call or win back) and the waiting list. Tapping a row
 * opens the single person, or the list when there are several. */
export function NeedsYou({
  lists,
  usageNotices,
  waiting,
  palette,
}: {
  lists: AttentionList[];
  usageNotices: { text: string; over: boolean; open: () => void }[];
  waiting: { count: number; top?: string } | null;
  palette: Palette;
}) {
  const t = useTranslations("dashboard.needs");
  const tAttention = useTranslations("dashboard.attention");
  const tWaitlist = useTranslations("dashboard.waitlist");
  const locale = useLocale();
  const [all, setAll] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const rows: Row[] = [];
  usageNotices.forEach((notice, index) =>
    rows.push({ key: `usage-${index}`, rank: notice.over ? 2 : 8, icon: "server-outline", tone: notice.over ? "danger" : "muted", title: notice.text, open: notice.open }),
  );
  for (const group of lists) {
    if (group.count === 0) continue;
    const { icon, tone, rank } = KINDS[group.kind];
    const href = (id: string) => (group.kind === "leads_due" ? `/lead/${id}` : `/client/${id}`);
    rows.push({
      key: group.kind,
      rank,
      icon,
      tone,
      title: tAttention(`kinds.${group.kind}`),
      detail: group.items.slice(0, 2).map((item) => item.name).join(", "),
      count: group.count,
      items: group.items.map((item) => ({
        id: item.id,
        name: item.name,
        subtitle: item.date ? tAttention(`dates.${group.kind}`, { date: formatDay(item.date, locale, { day: "numeric", month: "short" }) }) : tAttention("never"),
        open: () => router.push(href(item.id)),
      })),
    });
  }
  if (waiting && waiting.count > 0)
    rows.push({
      key: "waitlist",
      rank: 9,
      icon: "hourglass-outline",
      tone: "muted",
      title: tWaitlist("waiting", { count: waiting.count }),
      detail: waiting.top,
    });
  rows.sort((a, b) => a.rank - b.rank);
  const shown = all ? rows : rows.slice(0, VISIBLE);

  return (
    <View style={{ gap: 10 }}>
      <SectionTitle title={t("title")} palette={palette} />
      {rows.length === 0 ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("clear")}</Text>
        </Card>
      ) : (
        <Card palette={palette}>
          {shown.map((row, index) => {
            const isOpen = expanded === row.key;
            const toggle = row.items ? () => setExpanded(isOpen ? null : row.key) : row.open;
            return (
              <View key={row.key} style={{ borderTopWidth: index === 0 ? 0 : 1, borderColor: palette.border }}>
                <Pressable
                  accessibilityRole="button"
                  aria-expanded={row.items ? isOpen : undefined}
                  accessibilityLabel={[row.title, row.detail, row.count].filter(Boolean).join(", ")}
                  onPress={toggle}
                  style={{ flexDirection: "row", alignItems: "center", gap: 12, minHeight: 52, paddingVertical: 6 }}
                >
                  <Ionicons name={row.icon} size={20} color={row.tone === "muted" ? palette.muted : palette[row.tone]} />
                  <View style={{ flex: 1, gap: 1 }}>
                    <Text numberOfLines={1} style={{ color: palette.foreground, fontSize: 15, ...font.medium, textAlign: "left" }}>
                      {row.title}
                    </Text>
                    {row.detail && !isOpen ? (
                      <Text numberOfLines={1} style={{ color: palette.muted, fontSize: 13, ...font.regular, textAlign: "left" }}>
                        {row.detail}
                      </Text>
                    ) : null}
                  </View>
                  {row.count !== undefined && <Badge label={String(row.count)} tone={row.tone} palette={palette} />}
                  {row.items ? <Ionicons name={isOpen ? "chevron-up" : "chevron-down"} size={18} color={palette.muted} /> : null}
                </Pressable>
                {isOpen &&
                  row.items?.map((item) => (
                    <ListRow key={item.id} palette={palette} title={item.name} subtitle={item.subtitle} onPress={item.open} />
                  ))}
              </View>
            );
          })}
          {rows.length > VISIBLE && (
            <Pressable accessibilityRole="button" onPress={() => setAll(!all)} style={{ minHeight: 44, justifyContent: "center" }}>
              <Text style={{ color: palette.primaryInk, fontSize: 15, ...font.medium, textAlign: "left" }}>
                {all ? t("showLess") : t("showAll", { count: rows.length })}
              </Text>
            </Pressable>
          )}
        </Card>
      )}
    </View>
  );
}
