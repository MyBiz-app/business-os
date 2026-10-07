import type { components } from "@business-os/api-client";
import { router } from "expo-router";
import { useCallback } from "react";
import { Linking, Text } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { BackBar, Badge, ListRow } from "@business-os/app-kit/components/rows";
import { Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { WEB_URL } from "@business-os/app-kit/lib/env";
import { formatMoney } from "@business-os/app-kit/lib/money";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type ClientQuote = components["schemas"]["ClientQuote"];

const TONE = { sent: "primary", accepted: "success", declined: "muted", expired: "danger", draft: "muted" } as const;

/** My quotes (#44): the business's quotes for me; each opens its page (accept, pay the deposit). */
export default function Quotes() {
  const t = useTranslations("quotes");
  const tProfile = useTranslations("client.profile");
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();

  const load = useCallback(async () => {
    if (!business) return [] as ClientQuote[];
    return unwrap(await api.GET("/client/quotes", { params: scope }));
  }, [api, scope, business]);
  const { data, loading, reload } = useLoad(load);
  if (!business) return null;

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <BackBar label={tProfile("title")} palette={palette} onPress={() => router.back()} />
      <Heading palette={palette}>{t("title")}</Heading>
      {data && data.length === 0 && (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("none")}</Text>
        </Card>
      )}
      {data?.map((quote) => (
        <ListRow
          key={quote.token}
          palette={palette}
          title={`#${quote.number} · ${quote.title}`}
          subtitle={formatMoney(quote.total, quote.currency, locale)}
          trailing={<Badge label={t(`statuses.${quote.status}`)} tone={TONE[quote.status]} palette={palette} />}
          onPress={() => void Linking.openURL(`${WEB_URL}/q/${quote.token}`)}
        />
      ))}
    </Screen>
  );
}
