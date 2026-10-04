import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { unwrap } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

import { HoursForm } from "./hours-form";

export default async function StaffHoursPage({ params }: PageProps<"/team/[userId]/hours">) {
  const { userId } = await params;
  const t = await getTranslations();
  const { api, scope, tenant } = await getTenantFor("schedule.write");
  const team = unwrap(await api.GET("/staff", { params: scope }));
  const member = team.members.find((m) => m.user_id === userId);
  if (!member) notFound();
  const hours = unwrap(await api.GET("/staff/{user_id}/hours", { params: { ...scope, path: { user_id: userId } } }));
  // The week starts on Sunday in Israel and on Monday elsewhere (0 = Monday).
  const weekStartsOn = tenant.locale === "he" ? 6 : 0;

  return (
    <main className="enter mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/team" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("common.back")}
      </Link>
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold">{t("hours.title")}</h1>
        <p className="text-muted">
          {t("hours.subtitle", { name: member.email })}
        </p>
      </div>
      <section className="card p-6">
        <HoursForm
          userId={userId}
          weekStartsOn={weekStartsOn}
          initial={hours.blocks.map((block) => ({ weekday: block.weekday, starts: block.starts.slice(0, 5), ends: block.ends.slice(0, 5) }))}
        />
      </section>
    </main>
  );
}
