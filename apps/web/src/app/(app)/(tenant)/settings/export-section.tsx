import { getLocale, getTranslations } from "next-intl/server";

import { unwrap } from "@/lib/api";
import type { getTenant } from "@/lib/tenant";

import { downloadExport, requestExport } from "./export-actions";

/** Owners download everything the business holds: "your data, you can always leave". */
export async function ExportSection({ context }: { context: Awaited<ReturnType<typeof getTenant>> }) {
  const t = await getTranslations("dataExport");
  const locale = await getLocale();
  const { api, scope, tenant } = context;
  const exports = unwrap(await api.GET("/tenants/current/data-exports", { params: scope }));
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone: tenant.time_zone });
  const statusLabel = { building: t("status.building"), ready: t("status.ready"), failed: t("status.failed") } as Record<string, string>;
  const building = exports.some((item) => item.status === "building");

  return (
    <section aria-labelledby="export-heading" className="flex flex-col gap-4 card p-6">
      <div className="flex flex-col gap-1">
        <h2 id="export-heading" className="text-lg font-semibold">
          {t("title")}
        </h2>
        <p className="text-sm text-muted">{t("intro")}</p>
      </div>
      <form action={requestExport}>
        <button type="submit" disabled={building} className="btn-primary px-4 py-2.5 text-sm">
          {building ? t("building") : t("request")}
        </button>
      </form>
      {exports.length > 0 && (
        <ul className="flex flex-col gap-2 text-sm">
          {exports.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center justify-between gap-3">
              <span>
                {when.format(new Date(item.created_at))} · <span className="text-muted">{statusLabel[item.status]}</span>
              </span>
              {item.status === "ready" && item.expires_at && new Date(item.expires_at) > new Date() && (
                <form action={downloadExport}>
                  <input type="hidden" name="id" value={item.id} />
                  <button type="submit" className="btn-secondary px-4 py-2 text-sm">
                    {t("download")}
                  </button>
                </form>
              )}
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-muted">{t("note")}</p>
    </section>
  );
}
