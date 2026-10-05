import { useCallback } from "react";
import { Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useStaff } from "@/providers/staff-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

const WEEK = 7 * 24 * 60 * 60 * 1000;

/** What needs attention right now: open requests and the businesses that just joined. */
export default function Home() {
  const t = useTranslations("staffApp.home");
  const tLevels = useTranslations("platform.levels");
  const locale = useLocale();
  const { api, staff, can } = useStaff();
  const { palette } = useTheme();

  const load = useCallback(async () => {
    const [requests, businesses] = await Promise.all([
      can("inbox.manage") ? api.GET("/platform/contact-requests").then(unwrap) : [],
      can("businesses.read") ? api.GET("/platform/businesses").then(unwrap) : [],
    ]);
    return { requests, businesses };
  }, [api, can]);
  const { data, loading, reload } = useLoad(load);

  const open = (data?.requests ?? []).filter((r) => r.status !== "done");
  const since = Date.now() - WEEK;
  const fresh = (data?.businesses ?? []).filter((b) => new Date(b.created_at).getTime() > since);
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium" });

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <View style={{ gap: 4 }}>
        <Heading palette={palette}>{t("title")}</Heading>
        {staff && (
          <Text style={[styles.muted, { color: palette.muted }]}>
            {t("youAre", { level: tLevels(staff.level) })}
          </Text>
        )}
      </View>

      {open.length === 0 && fresh.length === 0 ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("nothing")}</Text>
        </Card>
      ) : null}

      {can("inbox.manage") && (
        <Card palette={palette}>
          <Text style={{ color: palette.muted, fontSize: 14 }}>{t("open")}</Text>
          <Text style={{ color: palette.foreground, fontSize: 32, fontWeight: "700" }}>{open.length}</Text>
        </Card>
      )}
      {can("businesses.read") && (
        <Card palette={palette}>
          <Text style={{ color: palette.muted, fontSize: 14 }}>{t("newBusinesses")}</Text>
          <Text style={{ color: palette.foreground, fontSize: 32, fontWeight: "700" }}>{fresh.length}</Text>
          {fresh.slice(0, 5).map((business) => (
            <Text key={business.id} style={[styles.muted, { color: palette.muted }]}>
              {business.name} · {date.format(new Date(business.created_at))}
            </Text>
          ))}
        </Card>
      )}
    </Screen>
  );
}
