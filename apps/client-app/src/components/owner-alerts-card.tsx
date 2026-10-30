import type { components } from "@business-os/api-client";
import { useEffect, useState } from "react";
import { Switch } from "react-native";
import { useTranslations } from "use-intl";

import { Text } from "@business-os/app-kit/components/text";
import { Card, styles } from "@business-os/app-kit/components/ui";
import { ListRow, RowGroup } from "@business-os/app-kit/components/rows";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useStaff } from "@/providers/staff-provider";

type Settings = components["schemas"]["AlertSettings"];

/** "Alerts on my phone": the owner chooses which things clients do on their own reach the phone.
 * The pushes themselves come from an hourly job; this only stores the choices. */
export function OwnerAlertsCard() {
  const t = useTranslations("business.alerts");
  const { api, scope, palette, tenant } = useStaff();
  const [data, setData] = useState<Settings | null>(null);
  const owner = tenant?.role === "owner";

  useEffect(() => {
    if (!owner) return;
    api
      .GET("/owner-alerts", { params: scope })
      .then(unwrap)
      .then(setData)
      .catch(() => undefined);
  }, [api, scope, owner]);

  if (!owner || !data) return null;

  const choose = async (
    kind: Settings["kinds"][number]["kind"],
    enabled: boolean,
  ) => {
    const before = data;
    setData({
      ...data,
      kinds: data.kinds.map((item) =>
        item.kind === kind ? { ...item, enabled } : item,
      ),
    });
    try {
      setData(
        unwrap(
          await api.PUT("/owner-alerts/{kind}", {
            params: { ...scope, path: { kind } },
            body: { enabled },
          }),
        ),
      );
    } catch {
      setData(before);
    }
  };

  return (
    <Card palette={palette}>
      <Text style={{ color: palette.foreground, fontWeight: "500" }}>
        {t("title")}
      </Text>
      <Text style={[styles.muted, { color: palette.muted }]}>
        {t("hint", {
          from: `${data.quiet_from_hour}:00`,
          until: `0${data.quiet_until_hour}:00`,
        })}
      </Text>
      <RowGroup palette={palette}>
        {data.kinds.map((item) => (
          <ListRow
            key={item.kind}
            palette={palette}
            title={t(`kinds.${item.kind}`)}
            trailing={
              <Switch
                value={item.enabled}
                onValueChange={(on) => void choose(item.kind, on)}
                accessibilityLabel={t(`kinds.${item.kind}`)}
                trackColor={{ true: palette.primary, false: palette.border }}
              />
            }
          />
        ))}
      </RowGroup>
    </Card>
  );
}
