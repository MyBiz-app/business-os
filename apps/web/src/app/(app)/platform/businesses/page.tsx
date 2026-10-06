import { isVertical } from "@business-os/verticals";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { ScrollRegion } from "@/components/scroll-region";
import { unwrap } from "@/lib/api";
import { getPlatformFor } from "@/lib/platform";
import { industryTexts } from "@/lib/verticals";

const PAGE_SIZE = 25;
const SORTS = ["newest", "name", "clients", "bookings", "ai"] as const;
type Sort = (typeof SORTS)[number];

/** Every business on the platform: search, sort and pages (filtered here; the list is small
 * enough today, see #63 for moving it into the API). */
export default async function PlatformBusinessesPage({ searchParams }: PageProps<"/platform/businesses">) {
  const t = await getTranslations();
  const { text } = industryTexts(t);
  const locale = await getLocale();
  const { api } = await getPlatformFor("businesses.read");
  const params = await searchParams;
  const search = typeof params.q === "string" ? params.q.trim() : "";
  const sort: Sort = SORTS.find((value) => value === params.sort) ?? "newest";
  const all = unwrap(await api.GET("/platform/businesses"));
  const needle = search.toLocaleLowerCase(locale);
  const found = all.filter(
    (b) => !needle || `${b.name} ${b.owner_email ?? ""}`.toLocaleLowerCase(locale).includes(needle),
  );
  const compare: Record<Sort, (a: (typeof all)[number], b: (typeof all)[number]) => number> = {
    newest: (a, b) => b.created_at.localeCompare(a.created_at),
    name: (a, b) => a.name.localeCompare(b.name, locale),
    clients: (a, b) => b.clients - a.clients,
    bookings: (a, b) => b.bookings_30d - a.bookings_30d,
    ai: (a, b) => b.ai_credits_30d - a.ai_credits_30d,
  };
  found.sort(compare[sort]);
  const pages = Math.max(1, Math.ceil(found.length / PAGE_SIZE));
  const page = Math.min(pages, Math.max(1, Number(params.page) || 1));
  const businesses = found.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const pageHref = (target: number) => {
    const query = new URLSearchParams();
    if (search) query.set("q", search);
    if (sort !== "newest") query.set("sort", sort);
    query.set("page", String(target));
    return `/platform/businesses?${query}`;
  };
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  const date = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", year: "2-digit" });

  return (
    <main className="enter mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex flex-col gap-1">
        <h1 id="businesses-heading" className="text-3xl font-bold">
          {t("platform.businessesTitle")}
        </h1>
        <p className="text-sm text-muted">{t("platform.subtitle")}</p>
      </div>
      <form role="search" className="flex flex-wrap items-end gap-3">
        <label className="flex min-w-60 flex-1 flex-col gap-1.5 text-sm font-medium">
          {t("platform.list.search")}
          <input type="search" name="q" defaultValue={search} className="control px-3 py-2 font-normal" />
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("platform.list.sort")}
          <select name="sort" defaultValue={sort} className="control px-3 py-2 font-normal">
            {SORTS.map((value) => (
              <option key={value} value={value}>
                {t(`platform.list.sorts.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="btn-secondary px-4 py-2">
          {t("platform.list.searchButton")}
        </button>
      </form>
      <p className="text-sm text-muted" aria-live="polite">{t("platform.list.count", { count: found.length })}</p>
      <ScrollRegion labelledBy="businesses-heading" className="rounded-2xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-surface text-muted">
            <tr>
              {(["name", "owner", "modules", "clients", "activeClients", "bookings30d", "aiCredits30d", "created"] as const).map((key) => (
                <th key={key} scope="col" className="px-3 py-2 text-start font-medium">
                  {t(`platform.columns.${key}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {businesses.map((business) => (
              <tr key={business.id} className="border-t border-border transition-colors hover:bg-primary/4">
                <td className="px-3 py-2">
                  <Link href={`/platform/businesses/${business.id}`} className="font-medium text-primary underline-offset-4 hover:underline" dir="auto">
                    {business.name}
                  </Link>
                  <div className="text-xs text-muted">{isVertical(business.vertical) ? text(business.vertical, "name") : business.vertical}</div>
                </td>
                <td className="max-w-56 truncate px-3 py-2" dir="ltr" title={business.owner_email ?? undefined}>
                  {business.owner_email ?? "—"}
                </td>
                <td className="whitespace-nowrap px-3 py-2">
                  {business.modules.length === 0 ? (
                    t("platform.coreOnly")
                  ) : (
                    <span title={business.modules.map((m) => t(`modules.names.${m as "client_app"}`)).join(", ")}>
                      {t("platform.list.modulesCount", { count: business.modules.length })}
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 tabular-nums">{number.format(business.clients)}</td>
                <td className="px-3 py-2 tabular-nums">{number.format(business.active_clients)}</td>
                <td className="px-3 py-2 tabular-nums">{number.format(business.bookings_30d)}</td>
                <td className="px-3 py-2 tabular-nums">{number.format(business.ai_credits_30d)}</td>
                <td className="whitespace-nowrap px-3 py-2">{date.format(new Date(business.created_at))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
      {pages > 1 && (
        <nav aria-label={t("platform.list.count", { count: found.length })} className="flex items-center justify-between text-sm">
          {page > 1 ? <Link href={pageHref(page - 1)} className="text-primary">{t("platform.list.previous")}</Link> : <span />}
          <span className="text-muted">{t("platform.list.pageOf", { page, pages })}</span>
          {page < pages ? <Link href={pageHref(page + 1)} className="text-primary">{t("platform.list.next")}</Link> : <span />}
        </nav>
      )}
    </main>
  );
}
