import { Hourglass } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import type { getTenant } from "@/lib/tenant";

/** "12 people are waiting for a spot": a hint that another class may be worth opening. Shown only to
 * people who see the schedule, and only when somebody waits. */
export async function WaitlistHint({ context }: { context: Pick<Awaited<ReturnType<typeof getTenant>>, "api" | "scope" | "tenant"> }) {
  const { api, scope, tenant } = context;
  if (!tenant.permissions.includes("schedule.read") || !tenant.waitlist_enabled) return null;
  const { data } = await api.GET("/waitlist/summary", { params: scope });
  if (!data || data.waiting === 0) return null;
  const t = await getTranslations("dashboard.waitlist");
  const top = data.services[0];

  return (
    <Link href="/schedule/waitlist" className="card card-hover flex items-center gap-4 p-5">
      <span aria-hidden="true" className="icon-tile size-10">
        <Hourglass className="size-5" />
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="font-semibold">{t("waiting", { count: data.waiting })}</span>
        {top && (
          <span dir="auto" className="text-sm text-muted">
            {t("top", { service: top.name, count: top.waiting })}
          </span>
        )}
      </span>
    </Link>
  );
}
