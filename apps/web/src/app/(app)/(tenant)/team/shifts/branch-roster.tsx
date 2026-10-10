import { AlertTriangle, ArrowRightLeft } from "lucide-react";
import { useTranslations } from "next-intl";

import { Avatar } from "@/components/avatar";
import { formatDay } from "@/lib/dates";

import type { BoardPerson, BoardShift } from "./shift-board";

type Branch = { id: string; name: string; color: string };

/** Who is on and when, a day at a time with one column per branch, so branches compare side
 * by side. The branch name and color head every column. */
export function BranchRoster({ days, today, locale, branches, shifts, people }: { days: string[]; today: string; locale: string; branches: Branch[]; shifts: BoardShift[]; people: BoardPerson[] }) {
  const t = useTranslations("shifts");
  const person = new Map(people.map((p) => [p.id, p]));
  return (
    <div className="flex flex-col gap-4">
      {days.map((day) => {
        const isToday = day === today;
        return (
          <section key={day} aria-label={formatDay(day, locale, { weekday: "long", day: "numeric", month: "long" })} className="card overflow-hidden p-0">
            <h2 className={`flex items-center gap-2 border-b border-border px-4 py-2.5 text-sm font-semibold ${isToday ? "bg-primary/10 text-primary" : "bg-surface-2"}`}>
              {formatDay(day, locale, { weekday: "long", day: "numeric", month: "long" })}
              {isToday && <span className="rounded-full bg-primary px-2 py-0.5 text-[0.6875rem] font-medium text-on-primary">{t("today")}</span>}
            </h2>
            <div className="grid divide-border max-sm:divide-y sm:divide-x sm:[grid-template-columns:repeat(var(--n),minmax(0,1fr))]" style={{ "--n": branches.length } as React.CSSProperties}>
              {branches.map((branch) => {
                const here = shifts.filter((s) => s.day === day && s.locationId === branch.id);
                return (
                  <div key={branch.id} className="flex min-w-0 flex-col gap-2 p-3">
                    <div className="flex items-center gap-2 border-b-2 pb-1.5 text-sm font-semibold" style={{ borderColor: branch.color }}>
                      <span aria-hidden="true" className="size-2.5 rounded-full" style={{ background: branch.color }} />
                      <span dir="auto" className="truncate">{branch.name}</span>
                      <span className="ms-auto text-xs font-normal text-muted">{t("onShift", { count: new Set(here.map((s) => s.userId)).size })}</span>
                    </div>
                    {here.length === 0 ? (
                      <p className="py-2 text-sm text-muted">{t("nobody")}</p>
                    ) : (
                      <ul className="flex flex-col gap-1.5">
                        {here.map((shift) => {
                          const who = person.get(shift.userId);
                          return (
                            <li key={shift.id} className="flex items-center gap-2.5 rounded-lg px-2 py-1.5" style={{ background: `color-mix(in oklab, ${branch.color} 10%, var(--surface))` }}>
                              <span dir="ltr" className="w-[6.5rem] shrink-0 text-sm font-semibold tabular-nums">{shift.starts}–{shift.ends}</span>
                              {who && <Avatar id={who.id} name={who.name} src={who.avatar} size="sm" />}
                              <span className="flex min-w-0 flex-col">
                                <span dir="auto" className="truncate text-sm font-medium">{who?.name}</span>
                                {(shift.position || shift.isCover) && (
                                  <span className="flex items-center gap-1 truncate text-xs text-muted">
                                    {shift.isCover && (
                                      <span className="inline-flex items-center gap-1 text-primary">
                                        <ArrowRightLeft aria-hidden="true" className="size-3" />
                                        {t("coverFrom", { branch: shift.homeName ?? "" })}
                                      </span>
                                    )}
                                    {shift.position && <span dir="auto">{shift.position}</span>}
                                  </span>
                                )}
                              </span>
                              {shift.warning && <AlertTriangle aria-label={t(`warnings.${shift.warning}`)} className="ms-auto size-4 shrink-0 text-warning" />}
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
