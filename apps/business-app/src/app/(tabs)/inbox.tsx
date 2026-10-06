import type { components } from "@business-os/api-client";
import { dayOf, formatDay, formatTime, todayIn } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Avatar, Badge, ListRow, PillRow } from "@business-os/app-kit/components/rows";
import { Button, Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { fullName } from "@business-os/app-kit/lib/names";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Lead = components["schemas"]["Lead"];
type Stage = Lead["stage"];
type View_ = "open" | Stage | "messages";

const OPEN: Stage[] = ["new", "contacted", "trial", "offer"];

/** Leads on the way to becoming clients, by stage, and the messages the business sent. Leads need
 * the CRM module, messages the WhatsApp module; the tab shows whichever the business has. */
export default function Inbox() {
  const t = useTranslations("business.leads");
  const tLeads = useTranslations("leads");
  const tMessages = useTranslations("business.messages");
  const tMessaging = useTranslations("messaging");
  const locale = useLocale();
  const { api, scope, tenant, palette, can } = useBusiness();
  const crm = tenant?.modules.includes("crm") ?? false;
  const messaging = tenant?.modules.includes("whatsapp") ?? false;
  const [view, setView] = useState<View_>(crm ? "open" : "messages");
  const tenantId = tenant?.id;

  const load = useCallback(async () => {
    if (!tenantId) return null;
    const [board, messages] = await Promise.all([
      crm ? api.GET("/leads", { params: scope }).then(unwrap) : Promise.resolve(null),
      messaging ? api.GET("/messages", { params: { ...scope, query: { limit: 50 } } }).then(unwrap) : Promise.resolve([]),
    ]);
    return { board, messages };
  }, [api, scope, tenantId, crm, messaging]);
  const { data, loading, reload } = useLoad(load);
  if (!tenant) return null;

  const today = todayIn(tenant.time_zone);
  const short = (day: string) => formatDay(day, locale, { day: "numeric", month: "short" });
  const leads = data?.board?.items ?? [];
  const count = (stage: Stage) => data?.board?.counts.find((c) => c.stage === stage)?.count ?? 0;
  const shown =
    view === "open"
      ? leads
          .filter((lead) => OPEN.includes(lead.stage))
          // Who to call back first: overdue follow-ups, then the newest.
          .sort((a, b) => (a.follow_up_on ?? "9999").localeCompare(b.follow_up_on ?? "9999") || b.created_at.localeCompare(a.created_at))
      : leads.filter((lead) => lead.stage === view);

  const options: { value: View_; label: string; sublabel?: string }[] = [
    ...(crm
      ? [
          { value: "open" as const, label: t("open"), sublabel: String(OPEN.reduce((sum, s) => sum + count(s), 0)) },
          ...(["new", "contacted", "trial", "offer", "won", "lost"] as Stage[]).map((stage) => ({
            value: stage,
            label: tLeads(`stages.${stage}`),
            sublabel: String(count(stage)),
          })),
        ]
      : []),
    ...(messaging ? [{ value: "messages" as const, label: tMessages("title") }] : []),
  ];

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <View style={{ flex: 1, gap: 2 }}>
          <Heading palette={palette}>{crm ? tLeads("title") : tMessages("title")}</Heading>
          {data?.board && (
            <Text style={[styles.muted, { color: data.board.follow_ups_due > 0 ? palette.primary : palette.muted }]}>
              {t("due", { count: data.board.follow_ups_due })}
            </Text>
          )}
        </View>
        {crm && can("clients.write") && (
          <Button label={tLeads("new")} palette={palette} onPress={() => router.push("/lead/new")} />
        )}
      </View>

      {options.length > 1 && <PillRow<View_> label={tLeads("pipeline")} options={options} value={view} onChange={setView} palette={palette} />}

      {view === "messages" ? (
        <View style={{ gap: 8 }}>
          <Text style={[styles.muted, { color: palette.muted }]}>{tMessaging("simulated")}</Text>
          {(data?.messages ?? []).length === 0 ? (
            <Card palette={palette}>
              <Text style={[styles.muted, { color: palette.muted }]}>{loading ? "…" : tMessaging("noMessages")}</Text>
            </Card>
          ) : (
            (data?.messages ?? []).map((message) => (
              <ListRow
                key={message.id}
                palette={palette}
                leading={<Avatar name={message.recipient_name ?? message.to_phone} palette={palette} size={36} />}
                title={message.recipient_name ?? message.to_phone}
                subtitle={`${message.body}\n${tMessaging(`channels.${message.channel}`)} · ${short(dayOf(message.created_at, tenant.time_zone))} ${formatTime(message.created_at, locale, tenant.time_zone)}`}
                trailing={
                  <Badge
                    label={tMessaging(`statuses.${message.status}`)}
                    tone={message.status === "failed" ? "danger" : "muted"}
                    palette={palette}
                  />
                }
                onPress={
                  message.client_id
                    ? () => router.push(`/client/${message.client_id}`)
                    : message.lead_id
                      ? () => router.push(`/lead/${message.lead_id}`)
                      : undefined
                }
              />
            ))
          )}
        </View>
      ) : shown.length === 0 ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{loading ? "…" : t("none")}</Text>
        </Card>
      ) : (
        <View style={{ gap: 8 }}>
          {shown.map((lead) => {
            const name = fullName(lead.first_name, lead.last_name);
            const due = lead.follow_up_on && lead.follow_up_on <= today && OPEN.includes(lead.stage);
            return (
              <ListRow
                key={lead.id}
                palette={palette}
                leading={<Avatar name={name} palette={palette} />}
                title={name}
                subtitle={[
                  lead.interest,
                  tLeads(`sources.${lead.source}`),
                  lead.follow_up_on && OPEN.includes(lead.stage) ? t("followUp", { date: short(lead.follow_up_on) }) : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
                trailing={
                  <Badge
                    label={due ? tLeads("due") : tLeads(`stages.${lead.stage}`)}
                    tone={due ? "danger" : lead.stage === "won" ? "success" : "muted"}
                    palette={palette}
                  />
                }
                onPress={() => router.push(`/lead/${lead.id}`)}
              />
            );
          })}
        </View>
      )}
    </Screen>
  );
}
