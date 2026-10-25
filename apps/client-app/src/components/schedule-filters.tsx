import Ionicons from "@expo/vector-icons/Ionicons";
import { useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { useTranslations } from "use-intl";

import { Chip } from "@business-os/app-kit/components/chip";
import { PressableScale } from "@business-os/app-kit/components/motion";
import { Sheet } from "@business-os/app-kit/components/sheet";
import { Text } from "@business-os/app-kit/components/text";
import { Button } from "@business-os/app-kit/components/ui";
import { ALL_BRANCHES, type BranchFilter } from "@business-os/app-kit/lib/branch-filter";
import { type Palette, radius } from "@business-os/app-kit/lib/theme";
import { BranchBar } from "@/components/branch-bar";
import { type ClassFilters, NO_FILTERS, activeFilterCount } from "@/lib/class-filters";
import type { Location } from "@/lib/use-locations";

type Option = { id: string; name: string };

type Props = {
  palette: Palette;
  branches: Location[];
  branchFilter: BranchFilter;
  onBranchChange: (filter: BranchFilter) => void;
  instructors: Option[];
  services: Option[];
  filters: ClassFilters;
  onFiltersChange: (filters: ClassFilters) => void;
};

/** The schedule's one filter: a single button (with a count of what is on) that opens a sheet with
 * branch, coach and class type, instead of up to three rows of chips above the first class. */
export function ScheduleFilters({
  palette,
  branches,
  branchFilter,
  onBranchChange,
  instructors,
  services,
  filters,
  onFiltersChange,
}: Props) {
  const t = useTranslations("client.schedule");
  const [open, setOpen] = useState(false);
  const branchOn = branchFilter.branchId || branchFilter.kind ? 1 : 0;
  const count = activeFilterCount(filters) + branchOn;
  const hasBranches = branches.length > 1;
  const hasCoaches = instructors.length > 1;
  const hasClasses = services.length > 1;
  if (!hasBranches && !hasCoaches && !hasClasses) return null;

  const clear = () => {
    onBranchChange(ALL_BRANCHES);
    onFiltersChange(NO_FILTERS);
  };

  return (
    <>
      <PressableScale
        accessibilityRole="button"
        accessibilityLabel={count > 0 ? t("filterActive", { count }) : t("filter")}
        onPress={() => setOpen(true)}
        style={[local.button, { backgroundColor: palette.surface, borderColor: count > 0 ? palette.primary : palette.border }]}
      >
        <Ionicons name="options-outline" size={18} color={palette.primary} />
        <Text style={[local.label, { color: palette.foreground }]}>{t("filter")}</Text>
        {count > 0 && (
          <View style={[local.badge, { backgroundColor: palette.primary }]}>
            <Text style={[local.badgeText, { color: palette.onPrimary }]}>{count}</Text>
          </View>
        )}
      </PressableScale>
      <Sheet
        visible={open}
        onClose={() => setOpen(false)}
        palette={palette}
        title={t("filter")}
        footer={
          <>
            <Button label={t("showResults")} palette={palette} onPress={() => setOpen(false)} />
            {count > 0 && <Button label={t("clearFilters")} variant="secondary" palette={palette} onPress={clear} />}
          </>
        }
      >
        {hasBranches && (
          <View style={local.group}>
            <Text style={[local.groupTitle, { color: palette.muted }]}>{t("branch")}</Text>
            <BranchBar branches={branches} filter={branchFilter} onChange={onBranchChange} palette={palette} />
          </View>
        )}
        {hasCoaches && (
          <View style={local.group}>
            <Text style={[local.groupTitle, { color: palette.muted }]}>{t("coach")}</Text>
            <ScrollView horizontal role="tablist" showsHorizontalScrollIndicator={false} contentContainerStyle={local.chips}>
              <Chip
                role="tab"
                label={t("allInstructors")}
                selected={!filters.instructorId}
                onPress={() => onFiltersChange({ ...filters, instructorId: null })}
                palette={palette}
              />
              {instructors.map((i) => (
                <Chip
                  key={i.id}
                  role="tab"
                  label={i.name}
                  selected={filters.instructorId === i.id}
                  onPress={() => onFiltersChange({ ...filters, instructorId: i.id })}
                  palette={palette}
                />
              ))}
            </ScrollView>
          </View>
        )}
        {hasClasses && (
          <View style={local.group}>
            <Text style={[local.groupTitle, { color: palette.muted }]}>{t("classType")}</Text>
            <ScrollView horizontal role="tablist" showsHorizontalScrollIndicator={false} contentContainerStyle={local.chips}>
              <Chip
                role="tab"
                label={t("allClasses")}
                selected={!filters.serviceId}
                onPress={() => onFiltersChange({ ...filters, serviceId: null })}
                palette={palette}
              />
              {services.map((sv) => (
                <Chip
                  key={sv.id}
                  role="tab"
                  label={sv.name}
                  selected={filters.serviceId === sv.id}
                  onPress={() => onFiltersChange({ ...filters, serviceId: sv.id })}
                  palette={palette}
                />
              ))}
            </ScrollView>
          </View>
        )}
      </Sheet>
    </>
  );
}

const local = StyleSheet.create({
  button: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingHorizontal: 14,
    minHeight: 44,
  },
  label: { fontSize: 15, fontWeight: "500" },
  badge: { minWidth: 20, height: 20, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", paddingHorizontal: 5 },
  badgeText: { fontSize: 12, fontWeight: "600" },
  group: { gap: 8 },
  groupTitle: { fontSize: 13, fontWeight: "600" },
  chips: { gap: 8, paddingVertical: 2 },
});
