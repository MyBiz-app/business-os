import { getLocale, getTranslations } from "next-intl/server";

import { unwrap } from "@/lib/api";
import type { getTenant } from "@/lib/tenant";

import { grantSupport, revokeSupport } from "./support-actions";

/** Owners let platform support look in (read-only, for a limited time) and see what it opened. */
export async function SupportSection({ context }: { context: Awaited<ReturnType<typeof getTenant>> }) {
  const t = await getTranslations("support");
  const locale = await getLocale();
  const { api, scope, tenant } = context;
  const status = unwrap(await api.GET("/support-access", { params: scope }));
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone: tenant.time_zone });

  return (
    <section aria-labelledby="support-heading" className="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-6">
      <div className="flex flex-col gap-1">
        <h2 id="support-heading" className="text-lg font-semibold">
          {t("title")}
        </h2>
        <p className="text-sm text-muted">{t("intro")}</p>
      </div>
      {status.active ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm font-medium">{t("activeUntil", { date: when.format(new Date(status.active.expires_at)) })}</p>
          <form action={revokeSupport}>
            <button type="submit" className="rounded-lg border border-border px-4 py-2 text-sm font-semibold text-danger">
              {t("revoke")}
            </button>
          </form>
        </div>
      ) : (
        <form action={grantSupport}>
          <button type="submit" className="rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-on-primary">
            {t("grant")}
          </button>
        </form>
      )}
      {status.visits.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-primary">{t("visits", { count: status.visits.length })}</summary>
          <ul className="mt-2 flex flex-col gap-1 text-muted">
            {status.visits.map((visit, i) => (
              <li key={i}>
                {when.format(new Date(visit.occurred_at))} · <span dir="ltr">{visit.actor_email}</span> ·{" "}
                <span dir="ltr">{visit.path}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
