import { getLocale, getTranslations } from "next-intl/server";

import { unwrap } from "@/lib/api";
import { formatDay, todayIn } from "@/lib/dates";
import { getTenantFor } from "@/lib/tenant";

import { reopenDay } from "./actions";
import { CloseDayForm } from "./close-day-form";
import { BackLink } from "@/components/back-link";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

/** Closed days (holidays): close a day, see upcoming closed days, reopen one. */
export default async function ClosedDaysPage() {
  const t = await getTranslations("schedule");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("schedule.write");
  const today = todayIn(tenant.time_zone);
  const days = unwrap(await api.GET("/closed-days", { params: scope }));

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/schedule" label={t("back")} />
      <PageHeader title={t("closedDays")} />
      <section aria-labelledby="close-heading" className="flex flex-col gap-4 card p-6">
        <h2 id="close-heading" className="text-lg font-semibold">
          {t("closeDay")}
        </h2>
        <CloseDayForm today={today} />
      </section>
      <section aria-labelledby="upcoming-closed-heading" className="flex flex-col gap-3 card p-6">
        <h2 id="upcoming-closed-heading" className="text-lg font-semibold">
          {t("upcomingClosed")}
        </h2>
        {days.length === 0 ? (
          <p className="text-sm text-muted">{t("noClosedDays")}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {days.map((day) => (
              <li key={day.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                <span>
                  <span className="font-medium">{formatDay(day.day, locale, { weekday: "long", day: "numeric", month: "long" })}</span>
                  {day.reason && (
                    <span className="text-muted" dir="auto">
                      {" "}
                      · {day.reason}
                    </span>
                  )}
                </span>
                <form action={reopenDay.bind(null, day.id)}>
                  <button type="submit" className="btn-link text-sm text-primary-ink underline-offset-4 hover:underline">
                    {t("reopenDay")}
                  </button>
                </form>
              </li>
            ))}
          </ul>
        )}
      </section>
    </Container>
  );
}
