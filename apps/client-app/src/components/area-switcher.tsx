import { useTranslations } from "use-intl";

import { Badge, ListRow, SectionTitle } from "@business-os/app-kit/components/rows";
import type { Area } from "@business-os/app-kit/lib/areas";
import type { Palette } from "@business-os/app-kit/lib/theme";
import { useAreas } from "@/providers/area-provider";

/** "Switch area": one row per identity, e.g. "My Studio · Owner" and "My Studio · Client".
 * Shows nothing when the person has a single area. */
export function AreaSwitcher({ palette }: { palette: Palette }) {
  const t = useTranslations("areas");
  const { areas, active, switchTo } = useAreas();
  if (!areas || areas.length < 2) return null;
  return (
    <>
      <SectionTitle title={t("switch")} palette={palette} />
      {areas.map((area) => (
        <ListRow
          key={area.key}
          palette={palette}
          title={area.name}
          subtitle={areaLabel(t, area)}
          trailing={area.key === active?.key ? <Badge label={t("current")} tone="primary" palette={palette} /> : null}
          onPress={() => void switchTo(area.key)}
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
