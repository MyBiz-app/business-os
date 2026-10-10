import { ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";

import { formatDay } from "@/lib/dates";

import type { BoardGap } from "./shift-board";

/** What the board falls short on: each stretch where a branch has fewer people on shift than its
 * coverage rules ask. */
export function CoverageBanner({ gaps, locale, showBranch }: { gaps: BoardGap[]; locale: string; showBranch: boolean }) {
  const t = useTranslations("shifts");
  if (gaps.length === 0) return null;
  return (
    <details className="card border-warning/40 bg-warning/5 p-0" open={gaps.length <= 3}>
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-medium [&::-webkit-details-marker]:hidden">
        <ShieldAlert aria-hidden="true" className="size-4 text-warning" />
        {t("coverage.banner", { count: gaps.length })}
      </summary>
      <ul className="flex flex-col gap-1 border-t border-border px-4 py-3 text-sm">
        {gaps.map((g) => (
          <li key={`${g.locationId}-${g.day}-${g.starts}`} className="flex flex-wrap items-center gap-x-2">
            <span className="font-medium">{formatDay(g.day, locale, { weekday: "short", day: "numeric", month: "short" })}</span>
            {showBranch && <span dir="auto" className="text-muted">{g.locationName}</span>}
            <span dir="ltr" className="tabular-nums">{g.starts}–{g.ends}</span>
            <span className="text-muted">{t("coverage.gap", { have: g.have, needed: g.needed })}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}
