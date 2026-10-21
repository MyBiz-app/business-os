import { useState } from "react";
import { useTranslations } from "use-intl";

import { Badge, ListRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { ErrorText } from "@business-os/app-kit/components/ui";
import type { Area } from "@business-os/app-kit/lib/areas";
import type { Palette } from "@business-os/app-kit/lib/theme";
import { useAreas } from "@/providers/area-provider";

/** "Switch area": one row per identity, e.g. "My Studio · Owner" and "My Studio · Client".
 * Shows nothing when the person has a single area. */
export function AreaSwitcher({ palette }: { palette: Palette }) {
  const t = useTranslations("areas");
  const { areas, active, switchTo } = useAreas();
  const [failed, setFailed] = useState(false);
  if (!areas || areas.length < 2) return null;
  const open = async (key: string) => {
    setFailed(false);
    try {
      await switchTo(key);
    } catch {
      setFailed(true);
    }
  };
  return (
    <>
      <SectionTitle title={t("switch")} palette={palette} />
      <ErrorText message={failed ? t("joinError") : null} palette={palette} />
      {areas.map((area) => (
        <ListRow
          key={area.key}
          palette={palette}
          title={area.name}
          subtitle={areaLabel(t, area)}
          trailing={area.key === active?.key ? <Badge label={t("current")} tone="primary" palette={palette} /> : null}
          onPress={() => void open(area.key)}
        />
      ))}
    </>
  );
}

function areaLabel(t: ReturnType<typeof useTranslations>, area: Area): string {
  if (area.kind === "platform") return t("platform");
  if (area.kind === "client") return t("client");
  return t(`role.${area.role ?? "staff"}`);
}
