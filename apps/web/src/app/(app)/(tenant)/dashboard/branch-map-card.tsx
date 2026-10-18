import { getTranslations } from "next-intl/server";

import { BranchMap } from "@/components/branch-map/branch-map";
import { loadBranchMap } from "@/lib/branch-map";
import type { getTenant } from "@/lib/tenant";

type Context = Awaited<ReturnType<typeof getTenant>>;

/** A small map of the branches for a business with two or more of them. Shown only when at least
 * two have a point on the map; one branch (or none placed yet) needs no map. */
export async function BranchMapCard({ context }: { context: Pick<Context, "api" | "scope" | "tenant"> }) {
  const branches = await loadBranchMap(context);
  if (branches.length < 2) return null;
  const t = await getTranslations("branchMap");
  return (
    <section aria-labelledby="branch-map-heading" className="card flex flex-col gap-3 p-6">
      <h2 id="branch-map-heading" className="text-lg font-semibold">
        {t("title")}
      </h2>
      <BranchMap branches={branches} currency={context.tenant.currency} variant="card" />
    </section>
  );
}
