"use client";

import { useCallback, useMemo, useState, type Key } from "react";

import type { DataTableColumn, SortState } from "./data-table";

type Options<Row> = {
  rows: Row[];
  rowKey: (row: Row) => Key;
  /** The value each sortable column sorts by (numbers sort as numbers, text by locale). */
  sortValues?: Record<string, (row: Row) => string | number | null | undefined>;
  locale?: string;
  initialSort?: SortState | null;
  columns?: DataTableColumn<Row>[];
};

/** State for an interactive `DataTable`: sort (client side, over the rows already loaded), row
 * selection, and which columns show. Pages that sort on the server keep using links and skip this. */
export function useDataTable<Row>({ rows, rowKey, sortValues = {}, locale, initialSort = null, columns = [] }: Options<Row>) {
  const [sort, setSort] = useState<SortState | null>(initialSort);
  const [selected, setSelected] = useState<ReadonlySet<Key>>(new Set());
  const [hidden, setHidden] = useState<ReadonlySet<string>>(new Set());

  const sorted = useMemo(() => {
    const value = sort && sortValues[sort.key];
    if (!sort || !value) return rows;
    const collator = new Intl.Collator(locale, { numeric: true, sensitivity: "base" });
    const sign = sort.direction === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const x = value(a);
      const y = value(b);
      if (x == null && y == null) return 0;
      if (x == null) return 1; // empty values go last in both directions
      if (y == null) return -1;
      return sign * (typeof x === "number" && typeof y === "number" ? x - y : collator.compare(String(x), String(y)));
    });
  }, [rows, sort, sortValues, locale]);

  const toggle = useCallback((key: Key) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);
  const toggleAll = useCallback(() => {
    setSelected((prev) => (sorted.every((row) => prev.has(rowKey(row))) ? new Set() : new Set(sorted.map(rowKey))));
  }, [sorted, rowKey]);
  const toggleColumn = useCallback((key: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  return {
    rows: sorted,
    sort,
    onSortChange: setSort,
    selected,
    toggle,
    toggleAll,
    clearSelection: useCallback(() => setSelected(new Set()), []),
    visibleColumns: columns.filter((col) => !hidden.has(col.key)),
    hidden,
    toggleColumn,
  };
}
