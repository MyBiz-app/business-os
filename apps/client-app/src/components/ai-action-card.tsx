import type { components } from "@business-os/api-client";
import { View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { Button, Card, styles } from "@business-os/app-kit/components/ui";
import { formatMoney } from "@business-os/app-kit/lib/money";
import type { Palette } from "@business-os/app-kit/lib/theme";

export type PendingAction = components["schemas"]["PendingAction"];

type Preview = {
  kind?: string;
  client?: string;
  service?: string;
  starts?: string;
  full?: boolean;
  dependent?: string;
  date?: string;
  hours?: number;
  description?: string;
  month?: string;
  clients?: number;
  total?: number;
  currency?: string;
  network?: string;
  account?: string;
  text?: string;
};

const TONE = { pending: "primary", executed: "success", rejected: "muted", expired: "muted", failed: "danger" } as const;

/** What the agent wants to do, in words, with the confirm and decline buttons while it waits. */
export function AiActionCard({
  action,
  palette,
  busy,
  onDecide,
}: {
  action: PendingAction;
  palette: Palette;
  busy: boolean;
  onDecide: (id: string, decision: "confirm" | "reject") => void;
}) {
  const t = useTranslations("assistant");
  const tAi = useTranslations("business.ai");
  const tNetworks = useTranslations("content.networks");
  const locale = useLocale();
  const p = action.preview as Preview;
  const month = p.month
    ? new Intl.DateTimeFormat(locale, { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${p.month}-15T12:00:00Z`))
    : "";

  let summary: string;
  if (p.kind === "log_time") {
    summary = t("logTimePreview", {
      hours: new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(p.hours ?? 0),
      client: p.client ?? "",
      description: p.description ?? "",
    });
  } else if (p.kind === "bill_month") {
    summary = t("billMonthPreview", {
      count: p.clients ?? 0,
      month,
      total: formatMoney(p.total ?? 0, p.currency ?? "ILS", locale),
    });
  } else if (p.kind === "publish_post") {
    summary = t("publishPreview", { network: p.network ? tNetworks(p.network as never) : "", account: p.account ?? "", text: p.text ?? "" });
  } else if (p.kind === "cancel_booking") {
    summary = t("cancelPreview", { client: p.client ?? "", service: p.service ?? "" });
  } else if (p.kind === "book_client") {
    summary = t("bookPreview", { client: p.dependent ? `${p.dependent} (${p.client ?? ""})` : (p.client ?? ""), service: p.service ?? "" });
  } else {
    summary = tAi("genericAction");
  }
  const when = p.starts ?? p.date;
  const waiting = action.status === "pending";

  return (
    <Card palette={palette}>
      <View style={{ gap: 8 }}>
        <Text style={[styles.muted, { color: palette.ai, fontWeight: "600" }]}>{t("needsConfirmation")}</Text>
        <Text style={{ color: palette.foreground, fontWeight: "500", fontSize: 15 }}>{summary}</Text>
        {when ? <Text style={[styles.muted, { color: palette.muted }]}>{when}</Text> : null}
        {p.full ? <Text style={[styles.muted, { color: palette.muted }]}>{t("fullWaitlist")}</Text> : null}
        {waiting ? (
          <View style={{ gap: 8 }}>
            <Button label={t("confirm")} palette={palette} busy={busy} onPress={() => onDecide(action.id, "confirm")} />
            <Button label={t("reject")} palette={palette} variant="secondary" disabled={busy} onPress={() => onDecide(action.id, "reject")} />
          </View>
        ) : (
          <Text accessibilityRole="text" style={{ color: palette[TONE[action.status]], fontWeight: "500" }}>
            {t(`statuses.${action.status}`)}
          </Text>
        )}
      </View>
    </Card>
  );
}
