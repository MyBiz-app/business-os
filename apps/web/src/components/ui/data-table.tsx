import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import type { Key, ReactNode } from "react";

import { ScrollRegion } from "@/components/scroll-region";

import { cx } from "./cx";

export type SortState = { key: string; direction: "asc" | "desc" };

export type DataTableColumn<Row> = {
  key: string;
  header: ReactNode;
  cell: (row: Row) => ReactNode;
  /** Numbers and amounts line up at the end edge (right in LTR, left in RTL). */
  align?: "start" | "end";
  /** Keep the cell on one line (dates, phone numbers, amounts). */
  nowrap?: boolean;
  /** Hide the column below this width, so a phone keeps the columns that matter. */
  hideBelow?: "sm" | "md" | "lg" | "xl";
  /** Extra classes for the cells of this column (a max width and truncate, for example). */
  className?: string;
  /** The cell names its row for screen readers (usually the first column): drawn as a row header. */
  rowHeader?: boolean;
  /** The header gets a sort button when `sort` and `onSortChange` are given. */
  sortable?: boolean;
};

type DataTableProps<Row> = {
  columns: DataTableColumn<Row>[];
  rows: Row[];
  /** A stable key per row. The index is there for rows with no id of their own. */
  rowKey: (row: Row, index: number) => Key;
  /** Names the table for screen readers: the id of the heading above it, or a label. */
  labelledBy?: string;
  label?: string;
  /** comfortable: 48px rows. compact: 36px rows for long lists. */
  density?: "comfortable" | "compact";
  /** Keeps the header in view while a long table scrolls inside its own region. */
  stickyHeader?: boolean;
  /** Shown instead of the table when there are no rows. */
  empty?: ReactNode;
  /** Adds classes to one row (a tint for a selected or overdue row). */
  rowClassName?: (row: Row) => string | undefined;
  /** A row that is also a link or button should set this so the pointer feedback matches. */
  rowInteractive?: boolean;
  /** Controlled sorting (use with `useDataTable`): the table only draws the state and reports clicks. */
  sort?: SortState | null;
  onSortChange?: (next: SortState | null) => void;
  /** Controlled row selection: a checkbox column is added. */
  selection?: { selected: ReadonlySet<Key>; onToggle: (key: Key) => void; onToggleAll: () => void; allLabel: string; rowLabel: (row: Row) => string };
  /** A footer row (totals), drawn inside the same table so the columns line up. */
  footer?: ReactNode;
  /** No border of its own, for a table that already sits inside a card (never a card in a card). */
  bare?: boolean;
  className?: string;
};

const HIDE = { sm: "hidden sm:table-cell", md: "hidden md:table-cell", lg: "hidden lg:table-cell", xl: "hidden xl:table-cell" } as const;
const PAD = { comfortable: "px-4 py-3", compact: "px-3 py-2" } as const;

function SortIcon({ direction }: { direction?: "asc" | "desc" }) {
  const Icon = direction === "asc" ? ArrowUp : direction === "desc" ? ArrowDown : ChevronsUpDown;
  return <Icon aria-hidden="true" className={cx("size-3.5 shrink-0", !direction && "opacity-50")} />;
}

/** The one table of the product (Calm): a flat card with a hairline, a quiet header, row hover and a
 * scroll region that keeps the page itself from scrolling sideways. It draws what it is given, so a
 * server page can use it as is; sorting and selection are controlled (see `useDataTable`). */
export function DataTable<Row>({
  columns,
  rows,
  rowKey,
  labelledBy,
  label,
  density = "comfortable",
  stickyHeader = false,
  empty,
  rowClassName,
  rowInteractive = true,
  sort,
  onSortChange,
  selection,
  footer,
  bare = false,
  className,
}: DataTableProps<Row>) {
  if (rows.length === 0 && empty) return <>{empty}</>;
  const pad = PAD[density];
  const cellBase = (col: DataTableColumn<Row>) =>
    cx(pad, col.align === "end" ? "text-end" : "text-start", col.nowrap && "whitespace-nowrap", col.hideBelow && HIDE[col.hideBelow]);
  return (
    <ScrollRegion labelledBy={labelledBy} label={label} className={cx(!bare && "card", stickyHeader && "max-h-[70vh] overflow-y-auto", className)}>
      <table className="w-full text-start text-sm">
        <thead className={cx("bg-subtle text-muted", stickyHeader && "sticky top-0 z-10")}>
          <tr>
            {selection && (
              <th scope="col" className={cx(pad, "w-10")}>
                <input
                  type="checkbox"
                  aria-label={selection.allLabel}
                  checked={rows.length > 0 && rows.every((row, index) => selection.selected.has(rowKey(row, index)))}
                  onChange={selection.onToggleAll}
                  className="size-4 accent-primary"
                />
              </th>
            )}
            {columns.map((col) => {
              const active = sort?.key === col.key ? sort.direction : undefined;
              const sortable = col.sortable && onSortChange;
              return (
                <th
                  key={col.key}
                  scope="col"
                  aria-sort={active ? (active === "asc" ? "ascending" : "descending") : undefined}
                  className={cx(cellBase(col), "font-medium")}
                >
                  {sortable ? (
                    <button
                      type="button"
                      onClick={() => onSortChange(!active ? { key: col.key, direction: "asc" } : active === "asc" ? { key: col.key, direction: "desc" } : null)}
                      className={cx("btn-plain inline-flex min-h-6 items-center gap-1 rounded-md font-medium hover:text-foreground", active && "text-foreground")}
                    >
                      {col.header}
                      <SortIcon direction={active} />
                    </button>
                  ) : (
                    col.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const key = rowKey(row, index);
            const selected = selection?.selected.has(key);
            return (
              <tr
                key={key}
                aria-selected={selection ? Boolean(selected) : undefined}
                className={cx("border-t border-border transition-colors", rowInteractive && "hover:bg-subtle", selected && "bg-primary-subtle", rowClassName?.(row))}
              >
                {selection && (
                  <td className={cx(pad, "w-10")}>
                    <input
                      type="checkbox"
                      aria-label={selection.rowLabel(row)}
                      checked={Boolean(selected)}
                      onChange={() => selection.onToggle(key)}
                      className="size-4 accent-primary"
                    />
                  </td>
                )}
                {columns.map((col) => {
                  const Cell = col.rowHeader ? "th" : "td";
                  return (
                    <Cell key={col.key} scope={col.rowHeader ? "row" : undefined} className={cx(cellBase(col), col.rowHeader && "font-medium", col.className)}>
                      {col.cell(row)}
                    </Cell>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
        {footer && <tfoot className="border-t border-border bg-subtle font-medium">{footer}</tfoot>}
      </table>
    </ScrollRegion>
  );
}
