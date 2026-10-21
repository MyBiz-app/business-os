import { getLocale, getTranslations } from "next-intl/server";

import { unwrap } from "@/lib/api";
import { statusPageUrl } from "@/lib/status";
import type { getTenant } from "@/lib/tenant";

import { grantSupport, revokeSupport } from "./support-actions";
import { CollapsibleSection } from "@/components/ui/collapsible-section";

/** Owners let platform support look in (read-only, for a limited time) and see what it opened. */
export async function SupportSection({ context }: { context: Awaited<ReturnType<typeof getTenant>> }) {
  const t = await getTranslations("support");
  const locale = await getLocale();
  const { api, scope, tenant } = context;
  const status = unwrap(await api.GET("/support-access", { params: scope }));
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone: tenant.time_zone });

  return (
    <section aria-labelledby="support-heading" className="flex flex-col gap-4 card p-6">
      <div className="flex flex-col gap-1">
        <h2 id="support-heading" className="text-lg font-semibold">
          {t("title")}
        </h2>
        <p className="text-sm text-muted">{t("intro")}</p>
        {statusPageUrl() && (
          <a href={statusPageUrl()} target="_blank" rel="noopener noreferrer" className="text-sm text-primary-ink underline-offset-4 hover:underline">
            {t("status")}
          </a>
        )}
      </div>
      {status.active ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm font-medium">{t("activeUntil", { date: when.format(new Date(status.active.expires_at)) })}</p>
          <form action={revokeSupport}>
            <button type="submit" className="btn-secondary px-4 py-2 text-sm text-danger">
              {t("revoke")}
            </button>
          </form>
        </div>
      ) : (
        <form action={grantSupport}>
          <button type="submit" className="btn-primary px-4 py-2.5 text-sm">
            {t("grant")}
          </button>
        </form>
      )}
      {status.visits.length > 0 && (
        <CollapsibleSection variant="inline" className="text-sm" title={<>{t("visitsTitle")} · {t("visits", { count: status.visits.length })}</>}>
          <ul className="flex flex-col gap-1 text-muted">
            {status.visits.map((visit, i) => (
              <li key={i}>
                {when.format(new Date(visit.occurred_at))} · <span dir="ltr">{visit.actor_email}</span> ·{" "}
                <span dir="ltr">{visit.path}</span>
                {visit.changed && <span className="ms-2 rounded-lg bg-warning/15 px-2 py-0.5 text-xs font-medium">{t("changed")}</span>}
              </li>
            ))}
          </ul>
        </CollapsibleSection>
      )}
    </section>
  );
}
