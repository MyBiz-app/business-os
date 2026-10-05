import { FlaskConical, MessageCircle, Trash2 } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { canWriteClients } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { deleteTemplate } from "./actions";
import { Composer } from "./composer";
import { TemplateForm } from "./templates";
import { isolate } from "@/lib/bidi";

const SUGGESTIONS = ["reminder", "comeback", "offer", "holiday"] as const;

export default async function MessagesPage() {
  const t = await getTranslations("messaging");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("clients.read");
  if (!tenant.modules.includes("whatsapp")) redirect("/upgrade/whatsapp");
  const writable = canWriteClients(tenant);
  const [audiences, templates, campaigns] = await Promise.all([
    api.GET("/messages/audiences", { params: scope }).then(unwrap),
    api.GET("/messages/templates", { params: scope }).then(unwrap),
    api.GET("/messages/campaigns", { params: scope }).then(unwrap),
  ]);
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone: tenant.time_zone });

  return (
    <main className="enter mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex items-center gap-3">
        <span className="icon-tile size-11">
          <MessageCircle aria-hidden="true" className="size-5" />
        </span>
        <div className="flex flex-col gap-0.5">
          <h1 className="text-3xl font-bold">{t("title")}</h1>
          <p className="text-sm text-muted">{t("subtitle")}</p>
        </div>
      </div>

      <p role="note" className="flex items-center gap-2 rounded-xl border border-warning/50 bg-warning/10 px-4 py-2 text-sm">
        <FlaskConical aria-hidden="true" className="size-4 shrink-0" />
        {t("simulated")}
      </p>

      {writable && (
        <section aria-labelledby="compose-heading" className="card flex flex-col gap-4 p-6">
          <h2 id="compose-heading" className="text-lg font-semibold">{t("compose")}</h2>
          <Composer
            audiences={audiences}
            templates={templates}
            suggestions={SUGGESTIONS.map((key) => ({ name: t(`suggestions.${key}.name`), body: t.raw(`suggestions.${key}.body`) as string }))}
            businessName={tenant.name}
            sampleName={t("sampleName")}
          />
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <section aria-labelledby="history-heading" className="card flex flex-col gap-4 p-6">
          <h2 id="history-heading" className="text-lg font-semibold">{t("history")}</h2>
          {campaigns.length === 0 ? (
            <p className="text-sm text-muted">{t("noCampaigns")}</p>
          ) : (
            <ol className="enter-items flex flex-col gap-3">
              {campaigns.map((campaign) => (
                <li key={campaign.id} className="flex flex-col gap-1.5 rounded-xl border border-border p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
                    <span className="font-medium text-foreground">
                      {t(`audiences.${campaign.audience}`)} · {t(`channels.${campaign.channel}`)}
                    </span>
                    <time dateTime={campaign.created_at}>{when.format(new Date(campaign.created_at))}</time>
                  </div>
                  <p dir="auto" className="line-clamp-3 whitespace-pre-wrap text-sm">{campaign.body}</p>
                  <p className="text-xs text-muted">
                    {t("sentTo", { count: campaign.recipients })}
                    {campaign.author_name && ` · ${campaign.author_name}`}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </section>

        <section aria-labelledby="templates-heading" className="card flex flex-col gap-4 p-6">
          <h2 id="templates-heading" className="text-lg font-semibold">{t("myTemplates")}</h2>
          {templates.length === 0 ? (
            <p className="text-sm text-muted">{t("noTemplates")}</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {templates.map((template) => (
                <li key={template.id} className="flex items-start justify-between gap-2 rounded-xl border border-border p-3">
                  <span className="flex min-w-0 flex-col gap-0.5">
                    <span className="font-medium">{template.name}</span>
                    <span dir="auto" className="line-clamp-2 text-xs text-muted">{template.body}</span>
                  </span>
                  {writable && (
                    <form action={deleteTemplate.bind(null, template.id)}>
                      <button
                        type="submit"
                        aria-label={t("deleteTemplate", { name: isolate(template.name) })}
                        className="rounded-lg p-1 text-muted transition-colors hover:bg-danger/10 hover:text-danger"
                      >
                        <Trash2 aria-hidden="true" className="size-4" />
                      </button>
                    </form>
                  )}
                </li>
              ))}
            </ul>
          )}
          {writable && (
            <div className="border-t border-border pt-4">
              <TemplateForm />
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
