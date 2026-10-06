import type { components } from "@business-os/api-client";
import { ArrowRight, CalendarX, FileHeart, PhoneCall, UserMinus } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { unwrap } from "@/lib/api";
import type { getTenant } from "@/lib/tenant";

type Kind = components["schemas"]["AttentionList"]["kind"];

/** Each list: its icon, where an item opens, and where "see all" leads. */
const KINDS: Record<Kind, { Icon: typeof UserMinus; item: (id: string) => string; all: string }> = {
  plan_ending: { Icon: CalendarX, item: (id) => `/clients/${id}`, all: "/reports#at-risk-heading" },
  inactive: { Icon: UserMinus, item: (id) => `/clients/${id}`, all: "/reports#at-risk-heading" },
  leads_due: { Icon: PhoneCall, item: (id) => `/leads/${id}`, all: "/leads" },
  health_review: { Icon: FileHeart, item: (id) => `/clients/${id}`, all: "/clients" },
};

/** What needs attention today (GET /attention): only the lists this person may see and that
 * have something in them; nothing at all when everything is in order. */
export async function AttentionPanel({ context }: { context: Pick<Awaited<ReturnType<typeof getTenant>>, "api" | "scope"> }) {
  const { api, scope } = context;
  const lists = unwrap(await api.GET("/attention", { params: scope }));
  if (lists.length === 0) return null;
  const t = await getTranslations("dashboard.attention");
  const locale = await getLocale();
  const date = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", timeZone: "UTC" });

  return (
    <section aria-labelledby="attention-heading" className="flex flex-col gap-4">
      <h2 id="attention-heading" className="text-lg font-semibold">
        {t("title")}
      </h2>
      <ul className="grid gap-4 md:grid-cols-2">
        {lists.map((list) => {
          const { Icon, item, all } = KINDS[list.kind];
          return (
            <li key={list.kind} className="card flex flex-col gap-3 p-5">
              <div className="flex items-center justify-between gap-3">
                <h3 className="flex items-center gap-2 font-semibold">
                  <span aria-hidden="true" className="icon-tile size-9">
                    <Icon className="size-4" />
                  </span>
                  {t(`kinds.${list.kind}`)}
                </h3>
                <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-sm font-bold text-primary">{list.count}</span>
              </div>
              <ul className="flex flex-col divide-y divide-border">
                {list.items.map((entry) => (
                  <li key={entry.id}>
                    <Link href={item(entry.id)} className="flex items-center justify-between gap-3 py-2 text-sm hover:text-primary">
                      <span className="truncate font-medium">{entry.name}</span>
                      <span className="shrink-0 text-muted">
                        {entry.date ? t(`dates.${list.kind}`, { date: date.format(new Date(entry.date)) }) : t("never")}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
              {list.count > list.items.length && (
                <Link href={all} className="mt-auto inline-flex items-center gap-1 text-sm font-medium text-primary underline-offset-4 hover:underline">
                  {t("all", { count: list.count })}
                  <ArrowRight aria-hidden="true" className="size-4 rtl:rotate-180" />
                </Link>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
