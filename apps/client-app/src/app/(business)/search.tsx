import type { components } from "@business-os/api-client";
import { dayOf, formatDay, formatTime } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Avatar, BackBar, Badge, ListRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Text } from "@business-os/app-kit/components/text";
import { EmptyState, Field, Heading, LoadError, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useStaff } from "@/providers/staff-provider";

type Hit = components["schemas"]["SearchHit"];
type Kind = Hit["kind"];

const MIN_CHARS = 2;
const KINDS: { kind: Kind; title: "clients" | "leads" | "staff" | "sessions" | "invoices" }[] = [
  { kind: "client", title: "clients" },
  { kind: "lead", title: "leads" },
  { kind: "staff", title: "staff" },
  { kind: "session", title: "sessions" },
  { kind: "invoice", title: "invoices" },
];
const DEBOUNCE_MS = 300;

/** One search box for the whole business: clients, leads, the team, classes and documents. The
 * server decides what this person may see (permissions, branches), as on the web's Cmd+K. */
export default function Search() {
  const t = useTranslations("business.search");
  const tBusiness = useTranslations("business");
  const tStatus = useTranslations("clients.statuses");
  const tStages = useTranslations("leads.stages");
  const tRoles = useTranslations("roles");
  const tDocs = useTranslations("invoices.kinds");
  const locale = useLocale();
  const { api, scope, tenant, palette } = useStaff();
  const [text, setText] = useState("");
  const [items, setItems] = useState<Hit[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const query = text.trim().slice(0, 100);
  const ready = query.length >= MIN_CHARS;

  useEffect(() => {
    if (!ready || !tenant) return;
    let current = true;
    const timer = setTimeout(() => {
      api
        .GET("/search", { params: { ...scope, query: { q: query } } })
        .then(unwrap)
        .then((result) => {
          if (!current) return;
          setFailed(false);
          setItems(result.items);
        })
        .catch(() => current && setFailed(true));
    }, DEBOUNCE_MS);
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [api, scope, tenant, query, ready, attempt]);

  const found = ready ? items : null;
  const zone = tenant?.time_zone ?? "UTC";
  const tag = (hit: Hit) => {
    if (!hit.tag) return null;
    try {
      if (hit.kind === "client") return tStatus(hit.tag as "active");
      if (hit.kind === "lead") return tStages(hit.tag as "new");
      if (hit.kind === "staff") return tRoles(hit.tag as "owner");
      if (hit.kind === "invoice") return tDocs(hit.tag as "quote");
    } catch {
      // An unknown value shows as it came.
    }
    return hit.tag;
  };
  const subtitle = (hit: Hit) =>
    [hit.kind === "session" && hit.at ? `${formatDay(dayOf(hit.at, zone), locale, { day: "numeric", month: "short" })} ${formatTime(hit.at, locale, zone)}` : null, hit.subtitle, hit.number ? `#${hit.number}` : null]
      .filter(Boolean)
      .join(" · ") || undefined;
  const open = (hit: Hit) => {
    if (hit.kind === "client") return () => router.push(`/client/${hit.id}`);
    if (hit.kind === "lead") return () => router.push(`/lead/${hit.id}`);
    if (hit.kind === "session") return () => router.push(`/session/${hit.id}`);
    return undefined;
  };

  return (
    <Screen palette={palette}>
      <BackBar label={tBusiness("today.title")} palette={palette} fallback="/today" />
      <Heading palette={palette}>{t("title")}</Heading>
      <Field label={t("title")} placeholder={t("hint")} palette={palette} value={text} onChangeText={setText} autoFocus autoCapitalize="none" returnKeyType="search" />
      {ready && failed ? (
        <LoadError palette={palette} onRetry={() => setAttempt((value) => value + 1)} />
      ) : !ready ? (
        <Text style={[styles.muted, { color: palette.muted }]}>{t("prompt")}</Text>
      ) : found && found.length === 0 ? (
        <EmptyState palette={palette} message={t("none")} icon="search-outline" />
      ) : (
        <View style={{ gap: 14 }}>
          {KINDS.map(({ kind, title }) => {
            const hits = (found ?? []).filter((hit) => hit.kind === kind);
            if (hits.length === 0) return null;
            return (
              <View key={kind} style={{ gap: 8 }}>
                <SectionTitle title={t(title)} palette={palette} />
                {hits.map((hit) => {
                  const label = tag(hit);
                  return (
                    <ListRow
                      key={`${hit.kind}-${hit.id}`}
                      palette={palette}
                      leading={hit.kind === "client" || hit.kind === "lead" || hit.kind === "staff" ? <Avatar name={hit.title} palette={palette} /> : undefined}
                      title={hit.title}
                      subtitle={subtitle(hit)}
                      trailing={label ? <Badge label={label} palette={palette} /> : undefined}
                      onPress={open(hit)}
                    />
                  );
                })}
              </View>
            );
          })}
        </View>
      )}
    </Screen>
  );
}
