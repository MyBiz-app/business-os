import { ArrowRight, Globe2, X } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { dismissWebsiteOffer } from "./website-offer-actions";

/** A one-time card for a business that has been here a while without a website: do your clients
 * have somewhere to find you? Closing it is permanent. */
export async function WebsiteOfferCard() {
  const t = await getTranslations("website.dashboardCard");
  return (
    <section aria-labelledby="website-offer-heading" className="card relative flex flex-wrap items-center gap-4 p-5">
      <Globe2 aria-hidden="true" className="size-8 shrink-0 text-primary-ink" />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <h2 id="website-offer-heading" className="text-lg font-semibold">{t("title")}</h2>
        <p className="text-sm text-muted">{t("body")}</p>
      </div>
      <Link href="/website" className="btn-plain btn-primary px-4 py-2.5">
        {t("cta")}
        <ArrowRight aria-hidden="true" className="size-4 rtl:rotate-180" />
      </Link>
      <form action={dismissWebsiteOffer}>
        <button type="submit" aria-label={t("dismiss")} title={t("dismiss")} className="btn-secondary size-9 p-0">
          <X aria-hidden="true" className="size-4" />
        </button>
      </form>
    </section>
  );
}
