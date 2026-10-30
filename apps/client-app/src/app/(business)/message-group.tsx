import type { components } from "@business-os/api-client";
import { useCallback, useEffect, useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { useTranslations } from "use-intl";

import { Chip } from "@business-os/app-kit/components/chip";
import { BackBar, PillRow } from "@business-os/app-kit/components/rows";
import { Text } from "@business-os/app-kit/components/text";
import { useToast } from "@business-os/app-kit/components/toast";
import { Button, Card, ErrorText, Field, Heading, Screen } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { confirm } from "@business-os/app-kit/lib/confirm";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useStaff } from "@/providers/staff-provider";

type Channel = components["schemas"]["CampaignCreate"]["channel"];
type Audience = components["schemas"]["AudienceCount"]["audience"];
type Preview = components["schemas"]["CampaignResult"];

const NET: Channel[] = ["push", "email", "popup"];
const PHONE: Channel[] = ["whatsapp", "sms"];
const SUGGESTIONS = ["reminder", "comeback", "offer", "holiday"] as const;

/** Writing to a group of clients from the phone: who, how, a template or your own words, a preview
 * of what the first person gets, and a confirmation with the number of people before it goes. */
export default function MessageGroup() {
  const t = useTranslations("business.broadcast");
  const tm = useTranslations("messaging");
  const tCommon = useTranslations("common");
  const toast = useToast();
  const { api, scope, tenant, palette, can } = useStaff();
  const [audience, setAudience] = useState<Audience>("active");
  const [channels, setChannels] = useState<Channel[]>(["push", "email"]);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [promotional, setPromotional] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const staff = audience === "staff";
  const usable = staff ? channels.filter((c) => NET.includes(c)) : channels;
  const withPhone = tenant?.modules.includes("whatsapp") ?? false;
  const offered = [...NET, ...(withPhone ? PHONE : [])];
  const needsSubject = usable.some((c) => NET.includes(c));
  // A stable key for effects: the list itself is a new array on every render.
  const channelKey = usable.join(",");

  const load = useCallback(
    async () => ({
      audiences: await api
        .GET("/messages/audiences", { params: { ...scope, query: { channels: (channelKey ? channelKey.split(",") : ["push"]) as Channel[] } } })
        .then(unwrap),
      templates: await api.GET("/messages/templates", { params: scope }).then((r) => r.data ?? []),
    }),
    // The counts follow the channels; the templates are loaded with them (cheap).
    [api, scope, channelKey],
  );
  const { data, reload } = useLoad(load);

  // The preview and the exact number of recipients follow what is typed (a dry run sends nothing).
  useEffect(() => {
    const sendOn = (channelKey ? channelKey.split(",") : []) as Channel[];
    if (!body.trim() || sendOn.length === 0) {
      setPreview(null);
      return;
    }
    const timer = setTimeout(() => {
      api
        .POST("/messages/campaigns", {
          params: scope,
          body: { audience, channel: sendOn[0] ?? "push", channels: sendOn, subject: subject.trim() || null, promotional, dry_run: true, body },
        })
        .then((r) => setPreview(r.data ?? null))
        .catch(() => setPreview(null));
    }, 450);
    return () => clearTimeout(timer);
  }, [api, scope, audience, channelKey, subject, promotional, body]);

  if (!tenant || !can("clients.write")) return null;

  const toggle = (channel: Channel) => {
    const next = channels.includes(channel) ? channels.filter((c) => c !== channel) : [...channels, channel];
    setChannels(next);
    if (audience === "open_leads" && !next.every((c) => PHONE.includes(c))) setAudience("active");
  };
  const count = preview?.recipients ?? 0;
  const ready = body.trim().length > 0 && usable.length > 0 && (!needsSubject || subject.trim().length > 0);

  const send = async () => {
    if (!ready) {
      setError(needsSubject && !subject.trim() ? t("needSubject") : t("needBody"));
      return;
    }
    setError(null);
    if (!(await confirm(tm("sendTo", { count }), preview?.preview ?? body, t("send"), tCommon("cancel")))) return;
    setSending(true);
    try {
      const result = unwrap(
        await api.POST("/messages/campaigns", {
          params: scope,
          body: { audience, channel: usable[0] ?? "push", channels: usable, subject: subject.trim() || null, promotional, dry_run: false, body },
        }),
      );
      toast("success", tm("sentTo", { count: result.recipients }));
      setBody("");
      setSubject("");
      setPreview(null);
      void reload();
    } catch {
      setError(tm("errors.generic"));
    } finally {
      setSending(false);
    }
  };

  const templates = [
    ...SUGGESTIONS.map((key) => ({ key, name: tm(`suggestions.${key}.name`), text: tm.raw(`suggestions.${key}.body`) as string })),
    ...(data?.templates ?? []).map((tpl) => ({ key: tpl.id, name: tpl.name, text: tpl.body })),
  ];

  return (
    <Screen palette={palette}>
      <BackBar label={t("back")} palette={palette} fallback="/clients" />
      <Heading palette={palette}>{t("title")}</Heading>

      <Text style={[local.label, { color: palette.foreground }]}>{tm("audience")}</Text>
      <PillRow<Audience>
        label={tm("audience")}
        palette={palette}
        value={audience}
        onChange={setAudience}
        options={(data?.audiences ?? [{ audience: "active" as Audience, recipients: 0 }])
          // Leads have only a phone number: they can be reached on WhatsApp or SMS only.
          .filter((a) => a.audience !== "open_leads" || (usable.length > 0 && usable.every((c) => PHONE.includes(c))))
          .map((a) => ({ value: a.audience, label: tm(`audiences.${a.audience}`), count: a.recipients }))}
      />

      <Text style={[local.label, { color: palette.foreground }]}>{tm("channel")}</Text>
      <View style={local.wrap}>
        {offered
          .filter((c) => !staff || NET.includes(c))
          .map((c) => (
            <Chip key={c} role="checkbox" label={tm(`channels.${c}`)} selected={usable.includes(c)} onPress={() => toggle(c)} palette={palette} />
          ))}
      </View>
      <Text style={[local.hint, { color: palette.muted }]}>{staff ? tm("staffChannelsHint") : tm("channelsHint")}</Text>

      <Text style={[local.label, { color: palette.foreground }]}>{tm("startFrom")}</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={local.row}>
        {templates.map((tpl) => (
          <Chip key={tpl.key} role="button" label={tpl.name} selected={body === tpl.text} onPress={() => setBody(tpl.text)} palette={palette} />
        ))}
      </ScrollView>

      {needsSubject ? (
        <Field label={tm("subject")} palette={palette} value={subject} onChangeText={setSubject} maxLength={150} />
      ) : null}
      <Field
        label={tm("text")}
        palette={palette}
        value={body}
        onChangeText={setBody}
        multiline
        maxLength={1000}
        textAlignVertical="top"
        style={local.body}
      />
      <Chip role="checkbox" label={tm("promotional")} selected={promotional} onPress={() => setPromotional(!promotional)} palette={palette} />
      {promotional ? <Text style={[local.hint, { color: palette.muted }]}>{tm("promotionalHint")}</Text> : null}

      {preview?.preview ? (
        <Card palette={palette}>
          <Text style={[local.hint, { color: palette.muted }]}>{t("previewCaption")}</Text>
          <Text style={[local.preview, { color: palette.foreground }]}>{preview.preview}</Text>
          {(preview.warnings ?? []).map((w) => (
            <Text key={w.variable} style={[local.hint, { color: palette.danger }]}>
              {tm("missingValue", { count: w.recipients, variable: w.variable })}
            </Text>
          ))}
        </Card>
      ) : null}

      <ErrorText message={error} palette={palette} />
      <Button label={tm("sendTo", { count })} palette={palette} busy={sending} disabled={!ready || count === 0} onPress={() => void send()} />
    </Screen>
  );
}

const local = StyleSheet.create({
  label: { fontSize: 15, fontWeight: "600", textAlign: "left" },
  hint: { fontSize: 13, textAlign: "left" },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  row: { flexDirection: "row", gap: 8, paddingVertical: 2 },
  body: { minHeight: 120, paddingTop: 12 },
  preview: { fontSize: 15, textAlign: "left" },
});
