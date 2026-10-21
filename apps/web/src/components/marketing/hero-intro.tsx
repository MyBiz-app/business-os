import { ChevronDown } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { DayClock } from "@/components/marketing/day-clock";

/**
 * The opening scene of the home page: "your business keeps working, even while you sleep". The
 * copy renders on the server (it is the first paint); beside it the 24-hour dial (DayClock) runs
 * from midnight to the visitor's own time while the day's events happen around it. Follows the
 * light and dark theme; reduced motion shows the finished dial without the sweep.
 */
export async function HeroIntro() {
  const t = await getTranslations("marketing.intro");

  return (
    <section className="dc-section relative isolate w-full overflow-hidden">
      <div aria-hidden="true" className="dc-backdrop pointer-events-none absolute inset-0 -z-10" />
      {/* Phones: headline, dial, then the text; wide screens: the copy beside the dial. */}
      <div className="page-gutter mx-auto grid min-h-[min(88svh,780px)] w-full max-w-7xl content-center items-center gap-x-16 gap-y-8 pb-20 pt-10 sm:pt-14 lg:grid-cols-[1fr_1.05fr]">
        <div className="mk-rise flex flex-col items-center gap-5 text-center lg:col-start-1 lg:row-start-1 lg:items-start lg:self-end lg:text-start">
          <p className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-4 py-1.5 text-sm font-medium text-muted backdrop-blur">
            <span aria-hidden="true" className="dc-live" />
            {t("eyebrow")}
          </p>
          <p className="text-4xl font-semibold leading-[1.08] tracking-tight sm:text-6xl">
            {t("title")}
            <br />
            <span className="dc-accent">{t("titleAccent")}</span>
          </p>
        </div>
        <div className="lg:col-start-2 lg:row-span-2 lg:row-start-1">
          <DayClock />
        </div>
        <div className="mk-rise flex flex-col items-center gap-6 text-center lg:col-start-1 lg:row-start-2 lg:items-start lg:self-start lg:text-start">
          <p className="max-w-xl text-base leading-relaxed text-muted sm:text-lg">{t("text")}</p>
          <Link href="/start" className="btn-primary btn-lg rounded-full px-7">
            {t("cta")}
          </Link>
        </div>
      </div>
      <a
        href="#hero"
        aria-label={t("scroll")}
        className="dc-cue absolute bottom-4 start-1/2 inline-flex size-10 -translate-x-1/2 items-center justify-center rounded-full border border-border text-muted transition-colors hover:bg-surface rtl:translate-x-1/2"
      >
        <ChevronDown aria-hidden="true" className="size-5" />
      </a>
    </section>
  );
}
