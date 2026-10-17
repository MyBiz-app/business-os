import type { components } from "@business-os/api-client";
import { CalendarClock, Plus, Target } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Avatar } from "@/components/avatar";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { SummaryTiles } from "@/components/ui/summary-tiles";
import { unwrap } from "@/lib/api";
import { formatDay, todayIn } from "@/lib/dates";
import { siteOrigin } from "@/lib/origin";
import { canWriteClients } from "@/lib/permissions";

import { getCrm } from "./crm";
import { CopyLink } from "./copy-link";
import { SOURCES } from "./sources";
import { StageFilter } from "./stage-filter";

type Lead = components["schemas"]["Lead"];
type Stage = Lead["stage"];
const PAGE_SIZE = 200; // the API's page limit
const MAX_PAGES = 50; // the API's offset limit (100,000 rows) is the real ceiling
const STAGES: Stage[] = ["new", "contacted", "trial", "offer", "won", "lost"];
/** The summary tiles open the board narrowed to what they count. */
const VIEWS = ["new30", "won30", "due"] as const;
type View = (typeof VIEWS)[number];
const DAY_MS = 86_400_000;
const STAGE_BAR: Record<Stage, string> = {
  new: "bg-electric",
  contacted: "bg-ai",
  trial: "bg-warning",
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
  // Which pipeline columns to show: none chosen (or all) means every column.
  const chosen = (Array.isArray(params.stage) ? params.stage : [params.stage]).filter((s): s is Stage => STAGES.includes(s as Stage));
  const shownStages = chosen.length > 0 ? STAGES.filter((s) => chosen.includes(s)) : STAGES;
  const view = VIEWS.find((v) => v === params.view);

  // "Show more" asks for one more page of leads: page `pages` is fetched along with those before it.
  const pages = Math.min(MAX_PAGES, Math.max(1, Number(params.pages) || 1));
  const boards = await Promise.all(
    Array.from({ length: pages }, async (_, index) =>
      unwrap(
        await api.GET("/leads", {
          params: { ...scope, query: { search: search || undefined, source, limit: PAGE_SIZE, offset: index * PAGE_SIZE } },
        }),
      ),
    ),
  );
  const all = { ...boards[0], items: boards.flatMap((b) => b.items) };
  const today = todayIn(tenant.time_zone);
  const monthAgo = new Date(`${today}T00:00:00Z`).getTime() - 30 * DAY_MS;
  const inView: Record<View, (lead: Lead) => boolean> = {
    new30: (lead) => new Date(lead.created_at).getTime() >= monthAgo,
    won30: (lead) => lead.stage === "won" && new Date(lead.stage_changed_at).getTime() >= monthAgo,
    due: (lead) => !!lead.follow_up_on && lead.follow_up_on <= today && !["won", "lost"].includes(lead.stage),
  };
  const board = { ...all, items: view ? all.items.filter(inView[view]) : all.items };
  const moreHref = (() => {
    const query = new URLSearchParams();
    if (search) query.set("q", search);
    if (source) query.set("source", source);
    if (chosen.length > 0) for (const stage of chosen) query.append("stage", stage);
    if (view) query.set("view", view);
    query.set("pages", String(pages + 1));
    return `/leads?${query}`;
  })();
  const inquiryLink = `${await siteOrigin()}/inquiry/${tenant.join_code}`;
  const rate = board.conversion_rate === null ? "-" : `${Math.round(board.conversion_rate * 100)}%`;
  const tiles = [
    { key: "new30", label: t("stats.new30"), value: board.new_last_30_days, href: "/leads?view=new30" },
    { key: "won30", label: t("stats.won30"), value: board.won_last_30_days, href: "/leads?view=won30" },
    { key: "conversion", label: t("stats.conversion"), value: rate, href: "/leads?stage=won&stage=lost", active: !view && chosen.length === 2 && chosen.includes("won") && chosen.includes("lost") },
    { key: "due", label: t("stats.followUps"), value: board.follow_ups_due, href: "/leads?view=due" },
  ].map((tile) => ({ ...tile, active: tile.active ?? view === tile.key }));

  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader
        title={
          <span className="flex items-center gap-3">
            <span className="icon-tile size-11">
              <Target aria-hidden="true" className="size-5" />
            </span>
            {t("title")}
          </span>
        }
        description={t("subtitle")}
        actions={
          canWriteClients(tenant) && (
            <Link href="/leads/new" className="btn-primary px-4 py-2.5">
              <Plus aria-hidden="true" className="size-4" />
              {t("new")}
            </Link>
          )
        }
      />

      <SummaryTiles label={t("stats.label")} tiles={tiles} />
      {view && (
        <p className="flex flex-wrap items-center gap-3 text-sm text-muted">
          {t("viewShowing", { view: t(`stats.${view === "due" ? "followUps" : view}`), count: board.items.length })}
          <Link href="/leads" scroll={false} className="btn-link underline-offset-4 hover:underline">
            {t("viewClear")}
          </Link>
        </p>
      )}

      <div className="flex flex-wrap items-end justify-between gap-4">
        <form role="search" className="flex flex-wrap items-end gap-3">
          {view && <input type="hidden" name="view" value={view} />}
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
          <StageFilter
            stages={STAGES.map((value) => ({ value, label: t(`stages.${value}`) }))}
            selected={shownStages}
            label={t("stageFilter")}
            allLabel={t("allStages")}
            countLabel={t("stagesShown", { shown: shownStages.length, total: STAGES.length })}
          />
          <button type="submit" className="btn-secondary px-4 py-2">
            {t("filter")}
          </button>
        </form>
        <CopyLink link={inquiryLink} label={t("inquiryLink")} copy={t("copy")} copied={t("copied")} />
      </div>

      {all.total > all.items.length && (
        <p role="status" className="flex flex-wrap items-center gap-3 text-sm text-muted">
          {t("truncated", { shown: all.items.length, total: all.total })}
          {pages < MAX_PAGES && (
            <Link href={moreHref} scroll={false} className="btn-secondary px-3 py-1.5">
              {t("showMore")}
            </Link>
          )}
        </p>
      )}

      {/* Scrolls sideways on narrow screens; focusable so keyboard users can scroll it too. */}
      <div role="region" aria-label={t("pipeline")} tabIndex={0} className="overflow-x-auto pb-2">
        <div className="grid auto-cols-[15rem] grid-flow-col gap-3 lg:auto-cols-fr">
          {shownStages.map((stage) => {
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
    </Container>
  );
}
