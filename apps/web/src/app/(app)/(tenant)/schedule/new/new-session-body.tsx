import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { isDay, todayIn } from "@/lib/dates";
import { canWriteSchedule } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { createSessions } from "../actions";
import { SessionForm } from "../session-form";

/** The new-session form: the page and the window over the schedule show the same thing. */
export async function NewSessionBody({ date }: { date?: string | string[] }) {
  const t = await getTranslations("schedule");
  const { tenant, api, scope, branch } = await getTenantFor("schedule.read");
  if (!canWriteSchedule(tenant)) redirect("/schedule");
  const options = unwrap(await api.GET("/sessions/options", { params: scope }));

  if (options.services.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-border p-8 text-center text-muted">
        {t("needService")}{" "}
        <Link href="/services/new" className="text-primary-ink underline">
          →
        </Link>
      </p>
    );
  }
  return (
    <SessionForm
      action={createSessions}
      options={options}
      // New sessions start in the current branch.
      defaults={{ date: isDay(date) ? date : todayIn(tenant.time_zone), place: branch ? `${branch}:` : "" }}
      submitLabel={t("create")}
      allowRepeat
    />
  );
}
