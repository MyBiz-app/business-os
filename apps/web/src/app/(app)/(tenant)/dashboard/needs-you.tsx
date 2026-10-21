import type { components } from "@business-os/api-client";
import { ArrowRight, BadgeCheck, CalendarX, CreditCard, FileHeart, Hourglass, Luggage, PhoneCall, Snowflake, UserMinus } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import type { ReactNode } from "react";

import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { unwrap } from "@/lib/api";
import { isolate } from "@/lib/bidi";
import type { getTenant } from "@/lib/tenant";

type Context = Awaited<ReturnType<typeof getTenant>>;
type Kind = components["schemas"]["AttentionList"]["kind"];

/** Rows shown before "Show all". */
const VISIBLE = 5;

/** Each attention list: its icon, tone, where it opens, and its place by urgency (lower is first). */
const KINDS: Record<Kind, { Icon: typeof UserMinus; tone: BadgeTone; href: string; rank: number }> = {
  license_expiring: { Icon: BadgeCheck, tone: "danger", href: "/settings/business#readiness-heading", rank: 1 },
  freeze_requests: { Icon: Snowflake, tone: "warning", href: "/clients", rank: 3 },
  health_review: { Icon: FileHeart, tone: "warning", href: "/clients", rank: 4 },
  leads_due: { Icon: PhoneCall, tone: "primary", href: "/leads", rank: 5 },
  plan_ending: { Icon: CalendarX, tone: "primary", href: "/reports#at-risk-heading", rank: 6 },
  inactive: { Icon: UserMinus, tone: "neutral", href: "/reports#at-risk-heading", rank: 7 },
};

type Row = { key: string; rank: number; Icon: typeof UserMinus; tone: BadgeTone; title: string; detail?: ReactNode; count?: number; href: string };

/** Everything that needs the owner today in ONE list, most urgent first: the subscription, the
 * licence, requests waiting for an answer, then who to call or win back. The pieces come from
 * GET /attention, the billing state and the waiting list; the server decides what each person may see. */
export async function NeedsYou({
  context,
  only,
  billingNotice,
  usageNotices,
  showAll,
  showAllHref,
  collapseHref,
}: {
  context: Pick<Context, "api" | "scope" | "tenant">;
  only?: readonly Kind[];
  billingNotice: { text: string; due: boolean } | null;
  usageNotices: string[];
  showAll: boolean;
  showAllHref: string;
  collapseHref: string;
}) {
  const { api, scope, tenant } = context;
  const t = await getTranslations("dashboard");
  const locale = await getLocale();
  const waitlistOn = tenant.permissions.includes("schedule.read") && tenant.waitlist_enabled;
  const [lists, waitlist] = await Promise.all([
    api.GET("/attention", { params: scope }).then(unwrap),
    waitlistOn ? api.GET("/waitlist/summary", { params: scope }).then((r) => r.data) : undefined,
  ]);

  const rows: Row[] = [];
  if (billingNotice) {
    rows.push({ key: "billing", rank: billingNotice.due ? 0 : 2, Icon: CreditCard, tone: billingNotice.due ? "danger" : "warning", title: billingNotice.text, href: "/settings/billing" });
  }
  usageNotices.forEach((text, index) => rows.push({ key: `usage-${index}`, rank: 8, Icon: Luggage, tone: "warning", title: text, href: "/settings/billing" }));
  for (const list of lists) {
    if (only && !only.includes(list.kind)) continue;
    const { Icon, tone, href, rank } = KINDS[list.kind];
    const names = list.items.slice(0, 2).map((entry) => isolate(entry.name));
    rows.push({
      key: list.kind,
      rank,
      Icon,
      tone,
      title: t(`attention.kinds.${list.kind}`),
      detail: names.length > 0 ? new Intl.ListFormat(locale, { type: "conjunction" }).format(names) : undefined,
      count: list.count,
      href,
    });
  }
  if (waitlist && waitlist.waiting > 0) {
    rows.push({
      key: "waitlist",
      rank: 9,
      Icon: Hourglass,
      tone: "neutral",
      title: t("waitlist.waiting", { count: waitlist.waiting }),
      detail: waitlist.services[0] ? t("waitlist.top", { service: isolate(waitlist.services[0].name), count: waitlist.services[0].waiting }) : undefined,
      href: "/schedule/waitlist",
    });
  }
  if (rows.length === 0) {
    return (
      <Card as="section" aria-labelledby="needs-heading" className="flex flex-col gap-1">
        <h2 id="needs-heading" className="text-lg font-semibold">
          {t("needs.title")}
        </h2>
        <p className="text-sm text-muted">{t("needs.clear")}</p>
      </Card>
    );
  }
  rows.sort((a, b) => a.rank - b.rank);
  const shown = showAll ? rows : rows.slice(0, VISIBLE);

  return (
    <Card as="section" aria-labelledby="needs-heading" padding="none" className="flex flex-col">
      <div className="p-4 pb-3 sm:p-5 sm:pb-3">
        <CardHeader titleId="needs-heading" title={t("needs.title")} actions={<Badge tone="primary">{rows.length}</Badge>} className="mb-0!" />
      </div>
      <ul className="flex flex-col divide-y divide-border border-t border-border">
        {shown.map(({ key, Icon, tone, title, detail, count, href }) => (
          <li key={key}>
            <Link href={href} className="group flex items-center gap-3 px-4 py-3 transition-colors hover:bg-subtle sm:px-5">
              <Badge tone={tone} className="size-8 shrink-0 justify-center p-0">
                <Icon aria-hidden="true" className="size-4" />
              </Badge>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-sm font-medium">{title}</span>
                {detail && <span className="truncate text-xs text-muted">{detail}</span>}
              </span>
              {count !== undefined && <span className="text-sm font-semibold tabular-nums">{count}</span>}
              <ArrowRight aria-hidden="true" className="size-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5 rtl:rotate-180 rtl:group-hover:-translate-x-0.5" />
            </Link>
          </li>
        ))}
      </ul>
      {rows.length > VISIBLE && (
        <Link
          href={showAll ? collapseHref : showAllHref}
          scroll={false}
          className="border-t border-border px-4 py-2.5 text-sm font-medium text-primary-ink underline-offset-4 hover:underline sm:px-5"
        >
          {showAll ? t("needs.showLess") : t("needs.showAll", { count: rows.length })}
        </Link>
      )}
    </Card>
  );
}
