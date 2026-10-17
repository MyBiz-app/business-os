import { ArrowLeft, ArrowRight } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

export type SummaryTile = {
  key: string;
  label: string;
  value: ReactNode;
  /** A second line (an amount, a period). */
  hint?: ReactNode;
  /** The filtered list this number opens. */
  href: string;
  /** The tile that matches the list shown now. */
  active?: boolean;
};

/** Numbers at the top of a list. Each one is a real link to the list filtered to exactly what
 * it counts, so the number and the rows under it always agree. */
export function SummaryTiles({ label, tiles }: { label: string; tiles: SummaryTile[] }) {
  return (
    <ul aria-label={label} className="enter-items grid grid-cols-2 gap-3 lg:grid-cols-4">
      {tiles.map((tile) => (
        <li key={tile.key}>
          <Link
            href={tile.href}
            scroll={false}
            aria-current={tile.active ? "true" : undefined}
            className={`card card-hover group flex h-full flex-col gap-1 p-4 ${tile.active ? "ring-2 ring-primary" : ""}`}
          >
            <span className="flex items-center justify-between gap-2 text-xs text-muted">
              {tile.label}
              <ArrowLeft aria-hidden="true" className="size-3.5 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100 ltr:hidden" />
              <ArrowRight aria-hidden="true" className="size-3.5 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100 rtl:hidden" />
            </span>
            <span className="text-2xl font-bold tabular-nums">{tile.value}</span>
            {tile.hint && <span className="text-xs text-muted">{tile.hint}</span>}
          </Link>
        </li>
      ))}
    </ul>
  );
}
