import type { components } from "@business-os/api-client";
import { ArrowRight, Clock } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { isolate } from "@/lib/bidi";
import { formatTime } from "@/lib/dates";

type Session = components["schemas"]["ScheduledSession"];
type Shift = components["schemas"]["Shift"];

const currentTime = () => Date.now();

/** Today as a timeline: each class or appointment with its time, how full it is, and a mark on
 * the ones that are yours, running now or already over. For an employee it is "my shift and my
 * classes today". */
export async function TodayCard({
  title,
  sessions,
  shifts,
  userId,
  timeZone,
  emptyText,
  scheduleHref,
}: {
  title: string;
  sessions: Session[];
  shifts: Shift[];
  userId: string;
  timeZone: string;
  emptyText: ReactNode;
  scheduleHref: string | null;
}) {
  const t = await getTranslations("dashboard");
  const ts = await getTranslations("schedule");
  const locale = await getLocale();
  const now = currentTime();
  const at = (iso: string) => formatTime(iso, locale, timeZone);

  return (
    <Card as="section" aria-labelledby="today-heading" padding="none" className="flex flex-col">
      <div className="p-4 pb-3 sm:p-5 sm:pb-3">
        <CardHeader
          titleId="today-heading"
          title={title}
          className="mb-0!"
          actions={
            scheduleHref && (
              <ButtonLink href={scheduleHref} variant="quiet">
                {t("openSchedule")}
                <ArrowRight aria-hidden="true" className="size-4 rtl:rotate-180" />
              </ButtonLink>
            )
          }
        />
      </div>
      {shifts.map((shift) => (
        <p key={shift.id} className="flex items-center gap-2 border-t border-border bg-subtle px-4 py-2.5 text-sm sm:px-5">
          <Clock aria-hidden="true" className="size-4 shrink-0 text-primary-ink" />
          <span className="font-medium">
            {t("myShift", { range: `\u2066${at(shift.starts_at)}-${at(shift.ends_at)}\u2069` })}
          </span>
          <span dir="auto" className="truncate text-muted">
            {isolate(shift.location_name)}
          </span>
        </p>
      ))}
      {sessions.length === 0 ? (
        <p className="border-t border-border px-4 py-6 text-sm text-muted sm:px-5">{emptyText}</p>
      ) : (
        <ul className="enter-items max-h-80 divide-y divide-border overflow-y-auto border-t border-border">
          {sessions.map((session) => {
            const cancelled = session.status === "cancelled";
            const over = !cancelled && Date.parse(session.ends_at) <= now;
            const live = !cancelled && !over && Date.parse(session.starts_at) <= now;
            const fill = session.capacity ? Math.min(session.booked / session.capacity, 1) : 0;
            const color = session.service.color ?? "var(--primary)";
            const spots = cancelled ? ts("cancelled") : ts("spotsLabel", { booked: session.booked, capacity: session.capacity });
            return (
              <li key={session.id}>
                <Link
                  href={`/schedule/${session.id}`}
                  className={`group flex items-center gap-4 px-4 py-3 transition-colors hover:bg-subtle sm:px-5 ${over ? "opacity-60" : ""}`}
                >
                  <span className="w-12 shrink-0 text-sm font-semibold tabular-nums" dir="ltr">
                    {at(session.starts_at)}
                  </span>
                  <span aria-hidden="true" className="h-9 w-1 shrink-0 rounded-full" style={{ backgroundColor: color }} />
                  <span className="flex min-w-0 flex-1 flex-col gap-1.5">
                    <span className="flex min-w-0 items-center gap-2">
                      <span className={`truncate text-sm font-medium ${cancelled ? "text-muted line-through" : ""}`}>{session.service.name}</span>
                      {session.instructor_user_id === userId && <Badge tone="primary">{t("yours")}</Badge>}
                      {live && <Badge tone="success" dot>{t("now")}</Badge>}
                      {over && <Badge>{t("done")}</Badge>}
                    </span>
                    <span className="text-xs text-muted sm:hidden">{spots}</span>
                    {!cancelled && (
                      <span aria-hidden="true" className="h-1.5 w-full max-w-48 overflow-hidden rounded-full bg-subtle">
                        <span className="block h-full rounded-full transition-[width] duration-700" style={{ width: `${fill * 100}%`, backgroundColor: color }} />
                      </span>
                    )}
                  </span>
                  <span className="hidden shrink-0 text-sm text-muted sm:block">{spots}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
