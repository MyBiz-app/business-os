import Ionicons from "@expo/vector-icons/Ionicons";
import { useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { useTranslations } from "use-intl";

import { Chip } from "@business-os/app-kit/components/chip";
import { PressableScale } from "@business-os/app-kit/components/motion";
import { ListRow } from "@business-os/app-kit/components/rows";
import { Text } from "@business-os/app-kit/components/text";
import {
  type BranchFilter,
  MAX_BRANCH_CHIPS,
  branchKinds,
  pickBranch,
  pickKind,
  visibleBranches,
} from "@business-os/app-kit/lib/branch-filter";
import type { Palette } from "@business-os/app-kit/lib/theme";
import type { Location } from "@/lib/use-locations";

type Props = {
  branches: Location[];
  filter: BranchFilter;
  onChange: (filter: BranchFilter) => void;
  palette: Palette;
};

/** The branch switcher on top of the calendar: one row of chips for up to four branches, or for
 * more a kind quick filter and a menu (a kind row next to a short branch row would say the same
 * thing twice). Shows nothing for a single branch. */
export function BranchBar({ branches, filter, onChange, palette }: Props) {
  const t = useTranslations("client.schedule");
  const tKinds = useTranslations("verticals");
  const [open, setOpen] = useState(false);
  if (branches.length < 2) return null;

  const kinds = branchKinds(branches);
  const kindLabel = (key: string) => (tKinds.has(`${key}.name`) ? tKinds(`${key}.name`) : key);
  const shown = visibleBranches(branches, { branchId: null, kind: filter.kind });
  const current = branches.find((b) => b.id === filter.branchId);

  return (
    <View style={local.wrap}>
      {kinds.length > 1 && branches.length > MAX_BRANCH_CHIPS && (
        <ScrollView horizontal role="tablist" showsHorizontalScrollIndicator={false} contentContainerStyle={local.chips}>
          <Chip
            role="tab"
            label={t("allBranches")}
            selected={!filter.kind}
            onPress={() => onChange(pickKind(filter, null, branches))}
            palette={palette}
          />
          {kinds.map((kind) => (
            <Chip
              key={kind}
              role="tab"
              label={kindLabel(kind)}
              selected={filter.kind === kind}
              onPress={() => onChange(pickKind(filter, kind, branches))}
              palette={palette}
            />
          ))}
        </ScrollView>
      )}
      {branches.length <= MAX_BRANCH_CHIPS ? (
        <ScrollView horizontal role="tablist" showsHorizontalScrollIndicator={false} contentContainerStyle={local.chips}>
          <Chip
            role="tab"
            label={t("allBranches")}
            selected={!filter.branchId}
            onPress={() => onChange(pickBranch(null))}
            palette={palette}
          />
          {shown.map((b) => (
            <Chip
              key={b.id}
              role="tab"
              label={b.name}
              selected={filter.branchId === b.id}
              onPress={() => onChange({ ...filter, branchId: b.id })}
              palette={palette}
            />
          ))}
        </ScrollView>
      ) : (
        <>
          <PressableScale
            accessibilityRole="button"
            accessibilityState={{ expanded: open }}
            accessibilityLabel={t("branch")}
            onPress={() => setOpen((o) => !o)}
            style={[local.menu, { backgroundColor: palette.surface, borderColor: palette.border }]}
          >
            <Ionicons name="location-outline" size={18} color={palette.primary} />
            <Text style={[local.menuLabel, { color: palette.foreground }]}>{current?.name ?? t("allBranches")}</Text>
            <Ionicons name={open ? "chevron-up" : "chevron-down"} size={18} color={palette.muted} />
          </PressableScale>
          {open && (
            <View style={[local.list, { backgroundColor: palette.surface, borderColor: palette.border }]}>
              <ListRow
                palette={palette}
                title={t("allBranches")}
                trailing={!filter.branchId ? <Ionicons name="checkmark" size={20} color={palette.primary} /> : null}
                onPress={() => {
                  onChange(pickBranch(null));
                  setOpen(false);
                }}
              />
              {shown.map((b) => (
                <ListRow
                  key={b.id}
                  palette={palette}
                  title={b.name}
                  subtitle={b.kind ? kindLabel(b.kind) : undefined}
                  trailing={filter.branchId === b.id ? <Ionicons name="checkmark" size={20} color={palette.primary} /> : null}
                  onPress={() => {
                    onChange({ ...filter, branchId: b.id });
                    setOpen(false);
                  }}
                />
              ))}
            </View>
          )}
        </>
      )}
    </View>
  );
}

const local = StyleSheet.create({
  wrap: { gap: 8 },
  chips: { gap: 8, paddingVertical: 2 },
  menu: { flexDirection: "row", alignItems: "center", gap: 8, borderWidth: 1, borderRadius: 16, paddingHorizontal: 14, paddingVertical: 12 },
  menuLabel: { flex: 1, fontSize: 15, fontWeight: "600" },
  list: { borderWidth: 1, borderRadius: 16, overflow: "hidden" },
});
