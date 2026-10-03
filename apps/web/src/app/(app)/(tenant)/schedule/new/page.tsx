import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { isDay, todayIn } from "@/lib/dates";
import { canWriteSchedule } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { createSessions } from "../actions";
import { SessionForm } from "../session-form";

export default async function NewSessionPage({ searchParams }: PageProps<"/schedule/new">) {
  const t = await getTranslations("schedule");
  const { tenant, api, scope } = await getTenant();
  if (!canWriteSchedule(tenant)) redirect("/schedule");
  const { date } = await searchParams;
  const options = unwrap(await api.GET("/sessions/options", { params: scope }));

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <h1 className="text-3xl font-bold">{t("newSession")}</h1>
      {options.services.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border p-8 text-center text-muted">
          {t("needService")}{" "}
          <Link href="/services/new" className="text-primary underline">
            →
          </Link>
        </p>
      ) : (
        <SessionForm
          action={createSessions}
          options={options}
          defaults={{ date: isDay(date) ? date : todayIn(tenant.time_zone) }}
          submitLabel={t("create")}
          allowRepeat
        />
      )}
    </main>
  );
}
