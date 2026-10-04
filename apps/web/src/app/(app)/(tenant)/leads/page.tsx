import type { components } from "@business-os/api-client";
import { CalendarClock, Inbox, Plus, Target, TrendingUp, Trophy } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Avatar } from "@/components/avatar";
import { unwrap } from "@/lib/api";
import { formatDay, todayIn } from "@/lib/dates";
import { siteOrigin } from "@/lib/origin";
import { canWriteClients } from "@/lib/permissions";

import { getCrm } from "./crm";
import { CopyLink } from "./copy-link";
import { SOURCES } from "./sources";

type Lead = components["schemas"]["Lead"];
type Stage = Lead["stage"];
const STAGES: Stage[] = ["new", "contacted", "trial", "offer", "won", "lost"];
const STAGE_BAR: Record<Stage, string> = {
  new: "bg-sky-500",
  contacted: "bg-violet-500",
  trial: "bg-amber-500",
  offer: "bg-primary",
  won: "bg-success",
  lost: "bg-muted",
};

export default async function LeadsPage({ searchParams }: PageProps<"/leads">) {
  const t = await getTranslations("leads");
  const locale = await getLocale();
  const { tenant, api, scope } = await getCrm();
  const params = await searchParams;
  const search = typeof params.q === "string" ? params.q : "";
  const source = SOURCES.find((s) => s === params.source);

  const board = unwrap(
    await api.GET("/leads", { params: { ...scope, query: { search: search || undefined, source } } }),
  );
  const today = todayIn(tenant.time_zone);
  const inquiryLink = `${await siteOrigin()}/inquiry/${tenant.join_code}`;
  const rate = board.conversion_rate === null ? "—" : `${Math.round(board.conversion_rate * 100)}%`;
  const stats = [
    { label: t("stats.new30"), value: board.new_last_30_days, icon: Inbox },
    { label: t("stats.won30"), value: board.won_last_30_days, icon: Trophy },
    { label: t("stats.conversion"), value: rate, icon: TrendingUp },
    { label: t("stats.followUps"), value: board.follow_ups_due, icon: CalendarClock },
  ];

  return (
    <main className="enter mx-auto flex w-full max-w-[96rem] flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="icon-tile size-11">
            <Target aria-hidden="true" className="size-5" />
          </span>
          <div className="flex flex-col gap-0.5">
            <h1 className="text-3xl font-bold">{t("title")}</h1>
            <p className="text-sm text-muted">{t("subtitle")}</p>
          </div>
        </div>
        {canWriteClients(tenant) && (
          <Link href="/leads/new" className="btn-primary px-4 py-2.5">
            <Plus aria-hidden="true" className="size-4" />
            {t("new")}
          </Link>
        )}
      </div>

      <ul className="enter-items grid grid-cols-2 gap-3 lg:grid-cols-4">
        {stats.map(({ label, value, icon: Icon }) => (
          <li key={label} className="card flex items-center gap-3 p-4">
            <span className="icon-tile size-10">
              <Icon aria-hidden="true" className="size-5" />
            </span>
            <div className="flex flex-col">
              <span className="text-2xl font-bold tabular-nums">{value}</span>
              <span className="text-xs text-muted">{label}</span>
            </div>
          </li>
        ))}
      </ul>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <form role="search" className="flex flex-wrap items-end gap-3">
          <label className="flex min-w-56 flex-col gap-1.5 text-sm font-medium">
            {t("search")}
            <input type="search" name="q" defaultValue={search} className="control px-3 py-2 font-normal" />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            {t("source")}
            <select name="source" defaultValue={source ?? ""} className="control px-3 py-2 font-normal">
              <option value="">{t("allSources")}</option>
              {SOURCES.map((value) => (
                <option key={value} value={value}>
                  {t(`sources.${value}`)}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" className="btn-secondary px-4 py-2">
            {t("filter")}
          </button>
        </form>
        <CopyLink link={inquiryLink} label={t("inquiryLink")} copy={t("copy")} copied={t("copied")} />
      </div>

      {/* Scrolls sideways on narrow screens; focusable so keyboard users can scroll it too. */}
      <div role="region" aria-label={t("pipeline")} tabIndex={0} className="-mx-6 overflow-x-auto px-6 pb-2">
        <div className="grid min-w-[58rem] grid-cols-6 gap-3">
          {STAGES.map((stage) => {
            const leads = board.items.filter((lead) => lead.stage === stage);
            const headingId = `stage-${stage}`;
            return (
              <section key={stage} aria-labelledby={headingId} className="flex flex-col gap-2 rounded-2xl bg-foreground/[0.03] p-2">
                <div className="flex items-center justify-between px-2 pt-1">
                  <h2 id={headingId} className="flex items-center gap-2 text-sm font-semibold">
                    <span aria-hidden="true" className={`size-2 rounded-full ${STAGE_BAR[stage]}`} />
                    {t(`stages.${stage}`)}
                  </h2>
                  <span className="rounded-full bg-surface px-2 text-xs font-medium tabular-nums ring-1 ring-border">
                    {leads.length}
                  </span>
                </div>
                {leads.length === 0 ? (
                  <p className="rounded-xl border border-dashed border-border px-3 py-6 text-center text-xs text-muted">
                    {t("emptyStage")}
                  </p>
                ) : (
                  <ol className="enter-items flex flex-col gap-2">
                    {leads.map((lead) => {
                      const name = [lead.first_name, lead.last_name].filter(Boolean).join(" ");
                      const due = lead.follow_up_on && !["won", "lost"].includes(stage) && lead.follow_up_on <= today;
                      return (
                        <li key={lead.id}>
                          <Link
                            href={`/leads/${lead.id}`}
                            className="card card-hover relative flex flex-col gap-2 overflow-hidden p-3 ps-4"
                          >
                            <span aria-hidden="true" className={`absolute inset-y-0 start-0 w-1 ${STAGE_BAR[stage]}`} />
                            <span className="flex items-center gap-2">
                              <Avatar id={lead.id} name={name} size="sm" />
                              <span dir="auto" className="truncate font-medium">{name}</span>
                            </span>
                            {lead.interest && (
                              <span dir="auto" className="line-clamp-2 text-xs text-muted">{lead.interest}</span>
                            )}
                            <span className="flex flex-wrap items-center gap-1.5 text-xs">
                              <span className="rounded-full bg-foreground/5 px-2 py-0.5">{t(`sources.${lead.source}`)}</span>
                              {lead.follow_up_on && !["won", "lost"].includes(stage) && (
                                <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${due ? "bg-danger/10 font-semibold" : "bg-foreground/5"}`}>
                                  <CalendarClock aria-hidden="true" className="size-3" />
                                  {due ? t("due") : formatDay(lead.follow_up_on, locale, { day: "numeric", month: "short" })}
                                </span>
                              )}
                              {lead.owner_name && <span className="ms-auto truncate text-muted">{lead.owner_name}</span>}
                            </span>
                          </Link>
                        </li>
                      );
                    })}
                  </ol>
                )}
              </section>
            );
          })}
        </div>
      </div>
    </main>
  );
}
