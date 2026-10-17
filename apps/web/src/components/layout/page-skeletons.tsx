import { getTranslations } from "next-intl/server";

import { Container, type ContainerSize } from "@/components/layout/container";

/** Skeletons for the heavy pages. Each keeps the width and the rough shape of the page it stands
 * in for (same `Container` size), so nothing shifts when the real page arrives. */

async function Shell({ size, children }: { size: ContainerSize; children: React.ReactNode }) {
  const t = await getTranslations("common");
  return (
    <Container as="main" size={size} aria-busy="true" className="flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <span role="status" className="sr-only">
        {t("loading")}
      </span>
      <div aria-hidden="true" className="flex flex-col gap-3">
        <div className="skeleton h-9 w-64" />
        <div className="skeleton h-4 w-96 max-w-full" />
      </div>
      {children}
    </Container>
  );
}

function Rows({ count }: { count: number }) {
  return (
    <div aria-hidden="true" className="card flex flex-col gap-3 p-5">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="skeleton h-11 w-full" />
      ))}
    </div>
  );
}

/** A toolbar (filters, search) over a table or list: clients, leads, invoices, payroll. */
export async function ListPageSkeleton({ size = "full" }: { size?: ContainerSize }) {
  return (
    <Shell size={size}>
      <div aria-hidden="true" className="flex flex-wrap gap-2">
        <div className="skeleton h-9 w-28" />
        <div className="skeleton h-9 w-28" />
        <div className="skeleton h-9 w-28" />
        <div className="skeleton h-9 w-56 ms-auto" />
      </div>
      <Rows count={8} />
    </Shell>
  );
}

/** A date bar over a calendar grid: the schedule and the shift board. */
export async function BoardPageSkeleton({ size = "full" }: { size?: ContainerSize }) {
  return (
    <Shell size={size}>
      <div aria-hidden="true" className="flex flex-wrap items-center gap-2">
        <div className="skeleton size-9" />
        <div className="skeleton h-9 w-24" />
        <div className="skeleton size-9" />
        <div className="skeleton h-9 w-44 ms-auto" />
      </div>
      <div aria-hidden="true" className="card grid grid-cols-7 gap-px overflow-hidden p-0">
        {Array.from({ length: 35 }, (_, i) => (
          <div key={i} className="skeleton h-24 rounded-none" />
        ))}
      </div>
    </Shell>
  );
}

/** Number cards over a list: sales, team, the AI team. */
export async function CardsPageSkeleton({ size = "full" }: { size?: ContainerSize }) {
  return (
    <Shell size={size}>
      <div aria-hidden="true" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="card flex flex-col gap-3 p-5">
            <div className="skeleton h-4 w-24" />
            <div className="skeleton h-8 w-32" />
          </div>
        ))}
      </div>
      <Rows count={5} />
    </Shell>
  );
}

/** A folder column beside a list: files. */
export async function SplitPageSkeleton({ size = "full" }: { size?: ContainerSize }) {
  return (
    <Shell size={size}>
      <div aria-hidden="true" className="grid gap-6 lg:grid-cols-[18rem_1fr]">
        <div className="card flex flex-col gap-2 p-3">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="skeleton h-9 w-full" />
          ))}
        </div>
        <Rows count={7} />
      </div>
    </Shell>
  );
}
