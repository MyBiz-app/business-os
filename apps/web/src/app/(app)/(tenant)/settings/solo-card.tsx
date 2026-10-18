import { Sprout } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { leaveSoloMode } from "./actions";

/** Shown in a solo business: the ways to "grow" (add a first employee or a second branch, which
 * opens the team and branch areas by itself) or to open everything at once. */
export async function SoloCard() {
  const t = await getTranslations("settings.solo");
  return (
    <section aria-labelledby="solo-heading" className="card-accent flex flex-col gap-4 p-6">
      <h2 id="solo-heading" className="flex items-center gap-2 text-lg font-semibold">
        <Sprout aria-hidden="true" className="size-5 text-primary-ink" />
        {t("title")}
      </h2>
      <p className="text-sm text-muted">{t("subtitle")}</p>
      <div className="flex flex-wrap gap-3">
        <Link href="/team" className="btn-secondary px-4 py-2 text-sm">
          {t("firstEmployee")}
        </Link>
        <Link href="/locations" className="btn-secondary px-4 py-2 text-sm">
          {t("secondBranch")}
        </Link>
        <form action={leaveSoloMode}>
          <button type="submit" className="btn-primary px-4 py-2 text-sm">
            {t("showAll")}
          </button>
        </form>
      </div>
    </section>
  );
}
