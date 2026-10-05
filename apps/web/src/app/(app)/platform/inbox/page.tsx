import { getLocale, getTranslations } from "next-intl/server";

import { unwrap } from "@/lib/api";
import { getPlatformFor } from "@/lib/platform";

/** Contact requests from the marketing site. */
export default async function PlatformInboxPage() {
  const t = await getTranslations();
  const locale = await getLocale();
  const { api } = await getPlatformFor("inbox.manage");
  const leads = unwrap(await api.GET("/platform/contact-requests"));
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });

  return (
    <main className="enter mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-6 py-10">
      <h1 className="text-3xl font-bold">{t("platform.leads")}</h1>
      {leads.length === 0 ? (
        <p className="text-muted">{t("platform.noLeads")}</p>
      ) : (
        <ul className="enter-items flex flex-col gap-3">
          {leads.map((lead) => (
            <li key={lead.id} className="card flex flex-col gap-2 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold" dir="auto">
                  {lead.name}
                  {lead.business && <span className="font-normal text-muted"> · {lead.business}</span>}
                </span>
                <span className="text-sm text-muted">{date.format(new Date(lead.created_at))}</span>
              </div>
              <p className="flex flex-wrap gap-3 text-sm" dir="ltr">
                <a href={`mailto:${lead.email}`} className="text-primary underline-offset-4 hover:underline">
                  {lead.email}
                </a>
                {lead.phone && <span>{lead.phone}</span>}
              </p>
              {lead.vertical && <p className="text-sm text-muted">{t(`marketing.contact.verticals.${lead.vertical as "fitness"}`)}</p>}
              {lead.message && (
                <p className="whitespace-pre-wrap text-sm" dir="auto">
                  {lead.message}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
