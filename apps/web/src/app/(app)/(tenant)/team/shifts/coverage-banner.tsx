import { ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";

import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { LinkSegmented } from "@/components/ui/link-segmented";
import { formatDay } from "@/lib/dates";

import type { BoardGap } from "./shift-board";

/** Managers choose whether drafts count: the plan, or only what the team already sees. */
type Roster = { current: "plan" | "published"; plan: string; published: string };

/** What the board falls short on: each stretch where a branch has fewer people on shift than its
 * coverage rules ask, and (for managers) who said they can work then and is free. */
export function CoverageBanner({ gaps, locale, showBranch, roster }: { gaps: BoardGap[]; locale: string; showBranch: boolean; roster?: Roster }) {
  const t = useTranslations("shifts");
  const tc = useTranslations("common");
  if (gaps.length === 0 && roster?.current !== "published") return null;
  return (
    <CollapsibleSection
      className="border-warning/40 bg-warning/5"
      defaultOpen={gaps.length <= 3}
      icon={<ShieldAlert aria-hidden="true" className="size-4 text-warning" />}
      title={t("coverage.banner", { count: gaps.length })}
      actions={
        roster ? (
          <LinkSegmented
            label={t("coverage.roster")}
            loadingLabel={tc("loading")}
            active={roster.current}
            options={(["plan", "published"] as const).map((mode) => ({ key: mode, label: t(mode === "plan" ? "coverage.rosterPlan" : "coverage.rosterPublished"), href: roster[mode] }))}
          />
        ) : undefined
      }
    >
      {gaps.length > 0 ? (
        <ul className="flex flex-col gap-2 text-sm">
          {gaps.map((g) => (
            <li key={`${g.locationId}-${g.day}-${g.starts}`} className="flex flex-col gap-0.5">
              <span className="flex flex-wrap items-center gap-x-2">
                <span className="font-medium">{formatDay(g.day, locale, { weekday: "short", day: "numeric", month: "short" })}</span>
                {showBranch && <span dir="auto" className="text-muted">{g.locationName}</span>}
                <span dir="ltr" className="tabular-nums">{g.starts}-{g.ends}</span>
                <span className="text-muted">{t("coverage.gap", { have: g.have, needed: g.needed })}</span>
              </span>
              {roster && (
                <span className="text-xs text-muted">
                  {g.available?.length ? t("coverage.canCover", { names: g.available.join(", ") }) : t("coverage.nobodyFree")}
                </span>
              )}
            </li>
          ))}
        </ul>
      ) : null}
    </CollapsibleSection>
  );
}
