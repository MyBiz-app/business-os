import type { components } from "@business-os/api-client";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { Avatar, BackBar, ListRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Text } from "@business-os/app-kit/components/text";
import { EmptyState, Field, Heading, LoadError, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { fullName } from "@business-os/app-kit/lib/names";
import { useStaff } from "@/providers/staff-provider";

type ClientItem = components["schemas"]["ClientListItem"];
type Lead = components["schemas"]["Lead"];

const MIN_CHARS = 2;
const SHOWN = 8;
const DEBOUNCE_MS = 300;

/** One search box for the whole business: clients and leads by name, phone or email. The same
 * lists the web search offers, each limited to what this person may read. */
export default function Search() {
  const t = useTranslations("business.search");
  const tBusiness = useTranslations("business");
  const { api, scope, tenant, palette, can } = useStaff();
  const [text, setText] = useState("");
  const [state, setState] = useState<{ clients: ClientItem[]; leads: Lead[] } | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const crm = tenant?.modules.includes("crm") ?? false;
  const query = text.trim();
  const ready = query.length >= MIN_CHARS;

  useEffect(() => {
    if (!ready || !tenant) return;
    let current = true;
    const timer = setTimeout(() => {
      Promise.all([
        can("clients.read")
          ? api.GET("/clients", { params: { ...scope, query: { search: query, limit: SHOWN, offset: 0 } } }).then(unwrap).then((r) => r.items)
          : Promise.resolve([] as ClientItem[]),
        crm && can("clients.read")
          ? api.GET("/leads", { params: { ...scope, query: { search: query, limit: SHOWN, offset: 0 } } }).then(unwrap).then((r) => r.items).catch(() => [] as Lead[])
          : Promise.resolve([] as Lead[]),
      ])
        .then(([clients, leads]) => {
          if (!current) return;
          setFailed(false);
          setState({ clients, leads });
        })
        .catch(() => current && setFailed(true));
    }, DEBOUNCE_MS);
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [api, scope, tenant, query, ready, crm, can, attempt]);

  const found = ready ? state : null;
  const clients = found?.clients ?? [];
  const leads = found?.leads ?? [];
  return (
    <Screen palette={palette}>
      <BackBar label={tBusiness("today.title")} palette={palette} fallback="/today" />
      <Heading palette={palette}>{t("title")}</Heading>
      <Field label={t("title")} placeholder={t("hint")} palette={palette} value={text} onChangeText={setText} autoFocus autoCapitalize="none" returnKeyType="search" />
      {ready && failed ? (
        <LoadError palette={palette} onRetry={() => setAttempt((value) => value + 1)} />
      ) : !ready ? (
        <Text style={[styles.muted, { color: palette.muted }]}>{t("prompt")}</Text>
      ) : found && clients.length === 0 && leads.length === 0 ? (
        <EmptyState palette={palette} message={t("none")} icon="search-outline" />
      ) : (
        <View style={{ gap: 14 }}>
          {clients.length > 0 && (
            <View style={{ gap: 8 }}>
              <SectionTitle title={t("clients")} palette={palette} />
              {clients.map((client) => {
                const name = fullName(client.first_name, client.last_name);
                return (
                  <ListRow
                    key={client.id}
                    palette={palette}
                    leading={<Avatar name={name} palette={palette} />}
                    title={name}
                    subtitle={[client.phone, client.email].filter(Boolean).join(" · ") || undefined}
                    onPress={() => router.push(`/client/${client.id}`)}
                  />
                );
              })}
            </View>
          )}
          {leads.length > 0 && (
            <View style={{ gap: 8 }}>
              <SectionTitle title={t("leads")} palette={palette} />
              {leads.map((lead) => {
                const name = fullName(lead.first_name, lead.last_name);
                return (
                  <ListRow
                    key={lead.id}
                    palette={palette}
                    leading={<Avatar name={name} palette={palette} />}
                    title={name}
                    subtitle={[lead.phone, lead.email].filter(Boolean).join(" · ") || undefined}
                    onPress={() => router.push(`/lead/${lead.id}`)}
                  />
                );
              })}
            </View>
          )}
        </View>
      )}
    </Screen>
  );
}
