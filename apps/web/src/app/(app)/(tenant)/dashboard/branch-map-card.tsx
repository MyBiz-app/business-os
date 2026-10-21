import { getTranslations } from "next-intl/server";

import { BranchMap } from "@/components/branch-map/branch-map";
import { loadBranchMap } from "@/lib/branch-map";
import type { getTenant } from "@/lib/tenant";

type Context = Awaited<ReturnType<typeof getTenant>>;

/** A small map on the dashboard: the branches when there are two or more with a point on the map,
 * and for a business with one branch the map of where its clients come from. Nothing until a
 * branch has a point. */
export async function BranchMapCard({ context }: { context: Pick<Context, "api" | "scope" | "tenant"> }) {
  const branches = await loadBranchMap(context);
  if (branches.length === 0) return null;
  const t = await getTranslations("branchMap");
  const single = branches.length === 1;
  return (
    <section aria-labelledby="branch-map-heading" className="card flex flex-col gap-3 p-6">
      <h2 id="branch-map-heading" className="text-lg font-semibold">
        {single ? t("clientsTitle") : t("title")}
      </h2>
      <BranchMap branches={branches} currency={context.tenant.currency} variant="card" originsOn={single} />
      {single && branches[0].origins.every((o) => o.latitude === null) && <p className="text-sm text-muted">{t("panel.originsEmpty")}</p>}
    </section>
  );
}
