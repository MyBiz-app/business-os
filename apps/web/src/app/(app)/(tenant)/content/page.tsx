import type { components } from "@business-os/api-client";
import { RefreshCw, Star } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";

import { Container } from "@/components/layout/container";
import { LinkSegmented } from "@/components/ui/link-segmented";
import { PageHeader } from "@/components/layout/page-header";
import { ColumnChart } from "@/components/charts/column-chart";
import { ConfirmDelete } from "@/components/form/confirm-delete";
import { SubmitButton } from "@/components/form/submit-button";
import { PrintButton } from "@/components/print-button";
import { unwrap } from "@/lib/api";
import { addDays, formatDay, isDay, todayIn } from "@/lib/dates";

import { disconnectAccount, refreshNow } from "./actions";
import { ConnectCards } from "./connect-cards";
import { ConnectNotice } from "./connect-notice";
import { CsvButton } from "./csv-button";
import { type Range, Filters } from "./filters";
import { Heatmap } from "./heatmap";
import { LineChart } from "./line-chart";
import { NetworkIcon } from "./network-icon";
import { getStudio } from "./studio";
import { CollapsibleSection } from "@/components/ui/collapsible-section";

type Kpi = components["schemas"]["Kpi"];

const KPI_ORDER = ["followers", "reach", "impressions", "video_views", "engagements", "engagement_rate_bp", "link_clicks", "profile_views"] as const;

function pick<T extends string>(value: string | string[] | undefined, allowed: readonly T[]): T | undefined {
  const first = Array.isArray(value) ? value[0] : value;
  return allowed.find((candidate) => candidate === first);
}

export default async function ContentPage({ searchParams }: PageProps<"/content">) {
  const t = await getTranslations("content");
  const tDash = await getTranslations("dashboard");
  const tc = await getTranslations("common");
  const locale = await getLocale();
  const { tenant, api, scope } = await getStudio();
  const canManage = tenant.permissions.includes("social.manage");
  const query = await searchParams;

  const [providers, accounts] = await Promise.all([
    api.GET("/social/providers", { params: scope }).then(unwrap),
    api.GET("/social/accounts", { params: scope }).then(unwrap),
  ]);

  const notice = <ConnectNotice query={query} canManage={canManage} />;
  const header = <PageHeader eyebrow={t("subtitle")} title={t("title")} />;
  if (accounts.length === 0) {
    return (
      <Container as="main" size="default" className="enter flex flex-1 flex-col gap-8 py-8">
        {header}
        {notice}
        <ConnectCards networks={providers.networks} canManage={canManage} withDemo={providers.demo_available} />
      </Container>
    );
  }

  // The view: networks, period and whether to compare, all kept in the address.
  const connectedNetworks = [...new Set(accounts.map((a) => a.network))];
  const chosen = (Array.isArray(query.network) ? query.network : [query.network]).filter((n): n is string => typeof n === "string" && connectedNetworks.includes(n));
  const range = pick(query.range, ["7", "30", "90", "month", "last_month", "custom"] as const) ?? "30";
  const today = todayIn(tenant.time_zone);
  const customFrom = typeof query.from === "string" && isDay(query.from) ? query.from : null;
  const customTo = typeof query.to === "string" && isDay(query.to) ? query.to : null;
  const monthStart = `${today.slice(0, 7)}-01`;
  const prevMonthEnd = addDays(monthStart, -1);
  const from =
    range === "month" ? monthStart : range === "last_month" ? `${prevMonthEnd.slice(0, 7)}-01` : range === "custom" && customFrom ? customFrom : addDays(range === "custom" && customTo ? customTo : today, -((range === "custom" ? 30 : Number(range)) - 1));
  const to = range === "month" ? today : range === "last_month" ? prevMonthEnd : range === "custom" && customTo ? customTo : today;
  const compare = query.compare === "1";
  const sort = pick(query.sort, ["views", "engagement"] as const) ?? "views";
  const selection = { networks: chosen.length > 0 ? chosen : undefined, from, to };

  const [dashboard, posts, audience] = await Promise.all([
    api.GET("/social/dashboard", { params: { ...scope, query: { ...selection, compare } } }).then(unwrap),
    api.GET("/social/posts/top", { params: { ...scope, query: { ...selection, sort, limit: 10 } } }).then(unwrap),
    api.GET("/social/audience", { params: { ...scope, query: { networks: selection.networks } } }).then(unwrap),
  ]);

  const compact = new Intl.NumberFormat(locale, { notation: "compact", maximumFractionDigits: 1 });
  const full = new Intl.NumberFormat(locale);
  const percent = new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 1, signDisplay: "exceptZero" });
  const rate = new Intl.NumberFormat(locale, { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const short = (day: string) => formatDay(day, locale, { day: "numeric", month: "numeric" });
  const allDemo = accounts.every((a) => a.is_demo);
  const display = (key: (typeof KPI_ORDER)[number], value: number) => (key === "engagement_rate_bp" ? rate.format(value / 10000) : compact.format(value));

  const change = (key: (typeof KPI_ORDER)[number], kpi: Kpi): string | null => {
    if (kpi.previous === null || kpi.previous === undefined) return null;
    if (key === "followers") {
      const net = kpi.value - kpi.previous;
      return net === 0 ? t("kpi.noChange") : t("kpi.growth", { value: `${net > 0 ? "+" : ""}${full.format(net)}` });
    }
    if (kpi.previous === 0) return null;
    const ratio = (kpi.value - kpi.previous) / kpi.previous;
    return ratio === 0 ? t("kpi.noChange") : t("kpi.vsPrevious", { value: percent.format(ratio) });
  };
  const trendUp = (kpi: Kpi) => (kpi.previous === null || kpi.previous === undefined ? null : kpi.value >= kpi.previous);

  // Sunday-first day names in the user's language, from a fixed Sunday.
  const weekdays = Array.from({ length: 7 }, (_, i) => new Intl.DateTimeFormat(locale, { weekday: "short", timeZone: "UTC" }).format(new Date(Date.UTC(2026, 0, 4 + i))));
  const bestCell = [...dashboard.heatmap].sort((a, b) => b.value - a.value)[0];
  const best = bestCell ? t("charts.best", { day: weekdays[bestCell.weekday], hour: `${String(bestCell.hour).padStart(2, "0")}:00` }) : null;

  const networkLabel = (network: string) => t(`networks.${network}` as "networks.facebook");
  const csv: (string | number)[][] = [
    [t("title"), `${from} - ${to}`],
    ...KPI_ORDER.map((key) => [t(`kpi.${key}`), dashboard.kpis[key]?.value ?? 0]),
    [],
    [t("posts.title")],
    ["", t("posts.views"), t("posts.engagement"), ""],
    ...posts.map((p) => [`${networkLabel(p.network)} · ${t(`kinds.${p.kind as "post"}`)} · ${p.published_at.slice(0, 10)}`, p.views, p.engagements, p.permalink ?? ""]),
  ];

  const sortHref = (value: string) => {
    const params = new URLSearchParams();
    for (const network of chosen) params.append("network", network);
    params.set("range", range);
    if (range === "custom") {
      params.set("from", from);
      params.set("to", to);
    }
    if (compare) params.set("compare", "1");
    params.set("sort", value);
    return `/content?${params.toString()}`;
  };

  const audienceGroups = (["age", "gender", "city"] as const).map((dimension) => ({ dimension, rows: audience.filter((a) => a.dimension === dimension) })).filter((g) => g.rows.length > 0);

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-8 py-8">
      <PageHeader
        eyebrow={t("subtitle")}
        title={t("title")}
        actions={
          <>
            <CsvButton label={t("export.csv")} filename={`content-${from}-${to}.csv`} rows={csv} />
            <PrintButton label={t("export.print")} logAs="report_print" />
          </>
        }
      />
      {notice}
      {allDemo && (
        <p role="note" className="rounded-xl border border-warning/40 bg-warning/10 px-4 py-3 text-sm font-medium">
          {t("demoBanner")}
        </p>
      )}
      <Filters networks={connectedNetworks} chosen={chosen} range={range as Range} from={from} to={to} compare={compare} sort={sort} />

      <section aria-label={t("title")} className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {KPI_ORDER.map((key) => {
          const kpi = dashboard.kpis[key];
          if (!kpi) return null;
          const note = change(key, kpi);
          const up = trendUp(kpi);
          return (
            <div key={key} className="card flex flex-col gap-1 p-4">
              <p className="text-sm text-muted">{t(`kpi.${key}`)}</p>
              <p className="text-2xl font-extrabold">
                <bdi>{display(key, kpi.value)}</bdi>
              </p>
              {note && <p className={`text-xs font-medium ${up === null ? "text-muted" : up ? "text-success-ink" : "text-danger"}`}>{note}</p>}
            </div>
          );
        })}
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="card min-w-0 p-6">
          {dashboard.followers_series.length === 0 ? (
            <p className="text-muted">{t("charts.noData")}</p>
          ) : (
            <LineChart
              title={t("charts.followersTitle")}
              series={dashboard.followers_series.map((s) => ({ key: s.network, label: networkLabel(s.network), points: s.points.map((p) => ({ day: p.day, value: p.followers })) }))}
              formatTick={(value) => compact.format(Math.round(value))}
              formatDay={short}
              tableLabel={tDash("showTable")}
              dayHeader={t("charts.day")}
            />
          )}
        </section>
        <section className="card min-w-0 p-6">
          {dashboard.video_views_weekly.length === 0 ? (
            <p className="text-muted">{t("charts.noData")}</p>
          ) : (
            <ColumnChart
              title={t("charts.videoViewsTitle")}
              unit={{ kind: "count" }}
              tableLabel={tDash("showTable")}
              headers={[t("charts.weekOf"), t("charts.views")]}
              columns={dashboard.video_views_weekly.map((w) => ({ key: w.week_start, label: short(w.week_start), value: w.views, display: full.format(w.views) }))}
            />
          )}
        </section>
        <section className="card min-w-0 p-6">
          <h2 className="mb-3 font-semibold">{t("charts.kindTitle")}</h2>
          {dashboard.engagement_by_kind.length === 0 ? (
            <p className="text-muted">{t("charts.noData")}</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {dashboard.engagement_by_kind.map((row) => {
                const top = Math.max(...dashboard.engagement_by_kind.map((r) => r.engagements), 1);
                return (
                  <li key={row.kind} className="flex flex-col gap-1">
                    <div className="flex justify-between gap-3 text-sm">
                      <span>{t(`kinds.${row.kind as "post"}`)}</span>
                      <bdi className="font-semibold">{full.format(row.engagements)}</bdi>
                    </div>
                    <div aria-hidden="true" className="h-2 rounded-full bg-foreground/5">
                      <div className="h-2 rounded-full bg-primary" style={{ width: `${Math.max(3, (row.engagements / top) * 100)}%` }} />
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
        <section className="card min-w-0 p-6">
          {dashboard.heatmap.length === 0 ? (
            <p className="text-muted">{t("charts.noData")}</p>
          ) : (
            <Heatmap cells={dashboard.heatmap} weekdays={weekdays} title={t("charts.heatmapTitle")} hint={t("charts.heatmapHint")} best={best} />
          )}
        </section>
      </div>

      <section aria-labelledby="top-posts" className="card min-w-0 flex flex-col gap-4 p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="top-posts" className="text-lg font-bold">
            {t("posts.title")}
          </h2>
          <div className="print:hidden">
            <LinkSegmented
              label={t("posts.title")}
              loadingLabel={tc("loading")}
              active={sort}
              options={(["views", "engagement"] as const).map((value) => ({ key: value, label: t(value === "views" ? "posts.sortViews" : "posts.sortEngagement"), href: sortHref(value) }))}
            />
          </div>
        </div>
        {posts.length === 0 ? (
          <p className="text-muted">{t("posts.empty")}</p>
        ) : (
          <ol className="flex flex-col divide-y divide-border">
            {posts.map((post) => (
              <li key={post.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
                <NetworkIcon network={post.network} size="sm" />
                <div className="min-w-[10rem] flex-1">
                  <p className="font-medium">{post.caption ?? t("posts.untitled")}</p>
                  <p className="text-xs text-muted">
                    {networkLabel(post.network)} · {t(`kinds.${post.kind as "post"}`)} · {formatDay(post.published_at.slice(0, 10), locale, { day: "numeric", month: "short" })}
                  </p>
                </div>
                <dl className="flex gap-5 text-sm">
                  <div>
                    <dt className="text-xs text-muted">{t("posts.views")}</dt>
                    <dd className="font-semibold"><bdi>{compact.format(post.views)}</bdi></dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">{t("posts.engagement")}</dt>
                    <dd className="font-semibold"><bdi>{compact.format(post.engagements)}</bdi></dd>
                  </div>
                  {post.avg_watch_sec !== null && (
                    <div>
                      <dt className="text-xs text-muted">{t("posts.watch")}</dt>
                      <dd className="font-semibold">{t("posts.seconds", { n: post.avg_watch_sec })}</dd>
                    </div>
                  )}
                </dl>
                {post.permalink && (
                  <a href={post.permalink} target="_blank" rel="noopener noreferrer" className="text-sm font-semibold text-primary-ink underline-offset-4 hover:underline print:hidden">
                    {t("posts.open")}
                  </a>
                )}
              </li>
            ))}
          </ol>
        )}
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section aria-labelledby="audience" className="card min-w-0 flex flex-col gap-4 p-6">
          <h2 id="audience" className="text-lg font-bold">
            {t("audience.title")}
          </h2>
          {audienceGroups.length === 0 ? (
            <p className="text-muted">{t("audience.empty")}</p>
          ) : (
            audienceGroups.map((group) => (
              <div key={group.dimension} className="flex flex-col gap-2">
                <h3 className="text-sm font-semibold text-muted">{t(`audience.${group.dimension}`)}</h3>
                <ul className="flex flex-col gap-1.5">
                  {group.rows.map((row) => (
                    <li key={row.label} className="grid grid-cols-[7rem_1fr_3rem] items-center gap-2 text-sm">
                      <span className="truncate">{group.dimension === "gender" ? t(`audience.${row.label as "female"}`) : row.label}</span>
                      <span aria-hidden="true" className="h-2 rounded-full bg-foreground/5">
                        <span className="block h-2 rounded-full bg-ai" style={{ width: `${row.share_bp / 100}%` }} />
                      </span>
                      <bdi className="text-end font-semibold">{percent.format(row.share_bp / 10000).replace("+", "")}</bdi>
                    </li>
                  ))}
                </ul>
              </div>
            ))
          )}
        </section>
        {dashboard.google_business && (
          <section aria-labelledby="google" className="card min-w-0 flex flex-col gap-4 p-6">
            <div className="flex items-center gap-3">
              <NetworkIcon network="google_business" size="sm" />
              <h2 id="google" className="text-lg font-bold">
                {t("google.title")}
              </h2>
            </div>
            <dl className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-sm text-muted">{t("google.rating")}</dt>
                <dd className="flex items-center gap-1 text-2xl font-extrabold">
                  <Star aria-hidden="true" className="size-5 fill-warning text-warning" />
                  <bdi>{dashboard.google_business.rating === null ? "-" : dashboard.google_business.rating.toFixed(1)}</bdi>
                </dd>
              </div>
              {(["reviews_new", "searches", "profile_views", "calls", "directions"] as const).map((key) => (
                <div key={key}>
                  <dt className="text-sm text-muted">{t(`google.${key === "reviews_new" ? "reviews" : key === "profile_views" ? "profileViews" : key}` as "google.calls")}</dt>
                  <dd className="text-2xl font-extrabold"><bdi>{compact.format(dashboard.google_business![key])}</bdi></dd>
                </div>
              ))}
            </dl>
          </section>
        )}
      </div>

      <section aria-labelledby="accounts" className="card flex flex-col gap-4 p-6 print:hidden">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="accounts" className="text-lg font-bold">
            {t("accounts.title")}
          </h2>
          {canManage && (
            <form action={refreshNow} className="flex items-center gap-3">
              <span className="text-xs text-muted">{t("accounts.refreshLimit")}</span>
              <SubmitButton variant="secondary">
                <RefreshCw aria-hidden="true" className="size-4" />
                {t("accounts.refresh")}
              </SubmitButton>
            </form>
          )}
        </div>
        <ul className="flex flex-col divide-y divide-border">
          {accounts.map((account) => (
            <li key={account.id} className="flex flex-wrap items-center gap-3 py-3">
              <NetworkIcon network={account.network} size="sm" />
              <div className="min-w-[10rem] flex-1">
                <p className="font-medium">
                  {account.name} {account.is_demo && <span className="ms-1 rounded-full bg-foreground/5 px-2 py-0.5 text-xs font-semibold text-muted">{t("accounts.demo")}</span>}
                </p>
                <p className="text-xs text-muted">
                  {account.last_synced_at ? t("accounts.lastSynced", { date: formatDay(account.last_synced_at.slice(0, 10), locale, { day: "numeric", month: "short" }) }) : t("accounts.never")}
                </p>
              </div>
              {canManage && <ConfirmDelete action={disconnectAccount.bind(null, account.id)} label={t("accounts.disconnect")} confirm={t("accounts.confirm")} />}
            </li>
          ))}
        </ul>
        <CollapsibleSection variant="inline" triggerClassName="font-semibold text-primary-ink" title={t("accounts.addMore")}>
          <div>
            <ConnectCards networks={providers.networks} canManage={canManage} withDemo={false} />
          </div>
        </CollapsibleSection>
      </section>
    </Container>
  );
}
