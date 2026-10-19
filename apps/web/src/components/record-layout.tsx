import type { ReactNode } from "react";

import { SectionNav, type SectionNavItem } from "./section-nav";

/**
 * The shape of a record card (client, lead): the inner menu in a column beside the content on wide
 * screens, a bar under the header on narrow ones, and the sections below it in one single column,
 * in the order the menu lists them. Inside a window (`menu` off) there is no menu, only the column.
 */
export function RecordLayout({ items, label, menu = true, children }: { items: SectionNavItem[]; label: string; menu?: boolean; children: ReactNode }) {
  if (!menu) return <div className="flex min-w-0 flex-col gap-6">{children}</div>;
  return (
    <div className="flex flex-col gap-4 lg:grid lg:grid-cols-[15rem_minmax(0,1fr)] lg:items-start lg:gap-6 xl:gap-10">
      <SectionNav items={items} label={label} />
      <div className="flex min-w-0 flex-col gap-6">{children}</div>
    </div>
  );
}
