import type { components } from "@business-os/api-client";
import { dayOf, formatDay, formatTime } from "@business-os/i18n/dates";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useState } from "react";
import { Linking, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Avatar, BackBar, Badge, PillRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { confirm } from "@business-os/app-kit/lib/confirm";
import { fullName } from "@business-os/app-kit/lib/names";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Stage = components["schemas"]["StageChange"]["stage"];
type Kind = components["schemas"]["ActivityCreate"]["kind"];

const STAGES: Stage[] = ["new", "contacted", "trial", "offer", "won", "lost"];
const KINDS: Kind[] = ["call", "message", "meeting", "note"];

/** One lead: reach them, move them along the pipeline, log what happened, and turn them into a
 * client when they sign up. */
export default function LeadScreen() {
  const { id, created } = useLocalSearchParams<{ id: string; created?: string }>();
  const t = useTranslations("business.leads");
  const tBusiness = useTranslations("business");
  const tClients = useTranslations("business.clients");
  const tMessages = useTranslations("business.messages");
  const tLeads = useTranslations("leads");
  const tMessaging = useTranslations("messaging");
  const locale = useLocale();
  const { api, scope, tenant, palette, can } = useBusiness();
  const [kind, setKind] = useState<Kind>("call");
  const [text, setText] = useState("");
  const [panel, setPanel] = useState<"log" | "message" | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(created ? t("added") : null);
  const [error, setError] = useState<string | null>(null);
  const tenantId = tenant?.id;
  const write = can("clients.write");

  const load = useCallback(async () => {
    if (!tenantId) return null;
    return unwrap(await api.GET("/leads/{lead_id}", { params: { ...scope, path: { lead_id: id } } }));
  }, [api, scope, id, tenantId]);
  const { data: lead, loading, reload } = useLoad(load);

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

  if (!lead || !tenant) {
    return (
      <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
        <BackBar label={tLeads("title")} palette={palette} onPress={() => router.back()} />
      </Screen>
    );
  }

  const name = fullName(lead.first_name, lead.last_name);
  const digits = lead.phone?.replace(/\D/g, "");
  const closed = lead.stage === "won" || lead.stage === "lost";
  const timeZone = tenant.time_zone;
  const when = (instant: string) =>
    `${formatDay(dayOf(instant, timeZone), locale, { day: "numeric", month: "short" })} ${formatTime(instant, locale, timeZone)}`;

  const move = (stage: Stage) =>
    act(async () => {
      unwrap(await api.POST("/leads/{lead_id}/stage", { params: { ...scope, path: { lead_id: id } }, body: { stage } }));
      return t("moved", { stage: tLeads(`stages.${stage}`) });
    });

  const log = () =>
    act(async () => {
      unwrap(
        await api.POST("/leads/{lead_id}/activities", { params: { ...scope, path: { lead_id: id } }, body: { kind, note: text.trim() } }),
      );
      return t("logged");
    });

  const send = () =>
    act(async () => {
      unwrap(await api.POST("/messages/direct", { params: scope, body: { lead_id: id, channel: "whatsapp", body: text } }));
      return tMessaging("sentOne");
    });

  const convert = async () => {
    const yes = await confirm(tLeads("convert"), t("convertConfirm", { name }), t("yes"), t("no"));
    if (!yes) return;
    await act(async () => {
      unwrap(await api.POST("/leads/{lead_id}/convert", { params: { ...scope, path: { lead_id: id } } }));
      return t("converted", { name });
    });
  };

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <BackBar label={tLeads("title")} palette={palette} onPress={() => router.back()} />

      <View style={{ flexDirection: "row", alignItems: "center", gap: 14 }}>
        <Avatar name={name} palette={palette} size={56} />
        <View style={{ flex: 1, gap: 4 }}>
          <Heading palette={palette}>{name}</Heading>
          <View style={{ flexDirection: "row", gap: 6, flexWrap: "wrap" }}>
            <Badge
              label={tLeads(`stages.${lead.stage}`)}
              tone={lead.stage === "won" ? "success" : lead.stage === "lost" ? "muted" : "primary"}
              palette={palette}
            />
            <Badge label={tLeads(`sources.${lead.source}`)} palette={palette} />
          </View>
        </View>
      </View>
      <Text style={[styles.muted, { color: palette.muted }]}>
        {[
          lead.interest,
          lead.follow_up_on && !closed
            ? t("followUp", { date: formatDay(lead.follow_up_on, locale, { day: "numeric", month: "short" }) })
            : null,
          lead.owner_name ? `${tLeads("owner")}: ${lead.owner_name}` : null,
        ]
          .filter(Boolean)
          .join(" · ")}
      </Text>

      <View accessibilityLiveRegion="polite">
        {notice ? <Text style={{ color: palette.success, fontWeight: "600" }}>{notice}</Text> : null}
        <ErrorText message={error} palette={palette} />
      </View>

      {(lead.phone || lead.email) && (
        <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
          {lead.phone && (
            <View style={{ flexGrow: 1, flexBasis: "30%" }}>
              <Button label={tClients("call")} palette={palette} onPress={() => void Linking.openURL(`tel:${lead.phone}`)} />
            </View>
          )}
          {lead.phone && (
            <View style={{ flexGrow: 1, flexBasis: "30%" }}>
              <Button
                label={tClients("whatsapp")}
                variant="secondary"
                palette={palette}
                onPress={() => void Linking.openURL(`https://wa.me/${digits}`)}
              />
            </View>
          )}
          {lead.email && (
            <View style={{ flexGrow: 1, flexBasis: "30%" }}>
              <Button
                label={tClients("email")}
                variant="secondary"
                palette={palette}
                onPress={() => void Linking.openURL(`mailto:${lead.email}`)}
              />
            </View>
          )}
        </View>
      )}

      {lead.client_id ? (
        <Card palette={palette}>
          <Text style={{ color: palette.foreground, fontWeight: "600" }}>{tLeads("isClient")}</Text>
          <Button label={tLeads("openClient")} palette={palette} onPress={() => router.push(`/client/${lead.client_id}`)} />
        </Card>
      ) : (
        write && (
          <Card palette={palette}>
            <Text style={{ color: palette.foreground, fontWeight: "600" }}>{t("stage")}</Text>
            <PillRow<Stage>
              label={t("stage")}
              palette={palette}
              value={lead.stage}
              onChange={(stage) => stage !== lead.stage && void move(stage)}
              options={STAGES.map((value) => ({ value, label: tLeads(`stages.${value}`) }))}
            />
            <Text style={[styles.muted, { color: palette.muted }]}>{tLeads("convertHint")}</Text>
            <Button label={tLeads("convert")} palette={palette} busy={busy} onPress={() => void convert()} />
          </Card>
        )
      )}

      {write && (
        <View style={{ flexDirection: "row", gap: 8 }}>
          <View style={{ flex: 1 }}>
            <Button
              label={t("log")}
              variant={panel === "log" ? "primary" : "secondary"}
              palette={palette}
              onPress={() => {
                setPanel(panel === "log" ? null : "log");
                setText("");
              }}
            />
          </View>
          {tenant.modules.includes("whatsapp") && lead.phone && (
            <View style={{ flex: 1 }}>
              <Button
                label={tClients("message")}
                variant={panel === "message" ? "primary" : "secondary"}
                palette={palette}
                onPress={() => {
                  setPanel(panel === "message" ? null : "message");
                  setText("");
                }}
              />
            </View>
          )}
        </View>
      )}

      {panel === "log" && (
        <Card palette={palette}>
          <Text style={{ color: palette.foreground, fontWeight: "600" }}>{tLeads("activityKind")}</Text>
          <PillRow<Kind>
            label={tLeads("activityKind")}
            palette={palette}
            value={kind}
            onChange={setKind}
            options={KINDS.map((value) => ({ value, label: tLeads(`activities.${value}`) }))}
          />
          <Field
            label={tLeads("activityNote")}
            palette={palette}
            value={text}
            onChangeText={setText}
            multiline
            style={{ minHeight: 80, paddingTop: 12, textAlignVertical: "top" }}
          />
          <Button label={tLeads("logActivity")} palette={palette} busy={busy} disabled={!text.trim()} onPress={() => void log()} />
        </Card>
      )}

      {panel === "message" && (
        <Card palette={palette}>
          <Field
            label={tMessages("to", { name })}
            palette={palette}
            value={text}
            onChangeText={setText}
            multiline
            maxLength={1000}
            style={{ minHeight: 80, paddingTop: 12, textAlignVertical: "top" }}
          />
          <Text style={[styles.muted, { color: palette.muted }]}>{tMessaging("simulated")}</Text>
          <Button label={tMessages("send")} palette={palette} busy={busy} disabled={!text.trim()} onPress={() => void send()} />
        </Card>
      )}

      <View style={{ gap: 8 }}>
        <SectionTitle title={tLeads("activityTitle")} palette={palette} />
        {lead.activities.map((activity) => (
          <Card key={activity.id} palette={palette}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <Badge label={tLeads(`activities.${activity.kind}`)} palette={palette} />
              <Text style={{ color: palette.muted, fontSize: 13, flex: 1, textAlign: "left" }}>
                {[activity.actor_name, when(activity.occurred_at)].filter(Boolean).join(" · ")}
              </Text>
            </View>
            {activity.to_stage ? (
              <Text style={{ color: palette.foreground, textAlign: "left" }}>
                {tLeads("movedTo", { stage: tLeads(`stages.${activity.to_stage}`) })}
              </Text>
            ) : null}
            {activity.note ? <Text style={{ color: palette.foreground, textAlign: "left" }}>{activity.note}</Text> : null}
          </Card>
        ))}
      </View>
    </Screen>
  );
}
