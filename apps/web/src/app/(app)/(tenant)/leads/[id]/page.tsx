import { Mail, Phone, UserCheck } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Avatar } from "@/components/avatar";
import { SubmitButton } from "@/components/form/submit-button";
import { unwrap } from "@/lib/api";
import { canWriteClients } from "@/lib/permissions";

import { convertLead, deleteLead, updateLead } from "../actions";
import { getCrm } from "../crm";
import { LeadForm } from "../lead-form";
import { ActivityForm, StageControl } from "./lead-controls";
import { Timeline } from "./timeline";

export default async function LeadPage({ params }: PageProps<"/leads/[id]">) {
  const { id } = await params;
  const t = await getTranslations("leads");
  const locale = await getLocale();
  const { tenant, api, scope } = await getCrm();
  const { data: lead, response } = await api.GET("/leads/{lead_id}", { params: { ...scope, path: { lead_id: id } } });
  if (response.status === 404 || !lead) notFound();
  const owners = unwrap(await api.GET("/leads/owners", { params: scope }));
  const writable = canWriteClients(tenant);
  const name = [lead.first_name, lead.last_name].filter(Boolean).join(" ");

  return (
    <main className="enter mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/leads" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("back")}
      </Link>

      <header className="card-accent flex flex-wrap items-center gap-4 p-6">
        <Avatar id={lead.id} name={name} size="lg" />
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <h1 dir="auto" className="truncate text-3xl font-bold">{name}</h1>
          <p className="text-sm text-muted">
            {t(`stages.${lead.stage}`)} · {t(`sources.${lead.source}`)}
            {lead.campaign && ` · ${lead.campaign}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {lead.phone && (
            <a href={`tel:${lead.phone}`} className="btn-secondary px-3 py-2 text-sm">
              <Phone aria-hidden="true" className="size-4" />
              <span dir="ltr">{lead.phone}</span>
            </a>
          )}
          {lead.email && (
            <a href={`mailto:${lead.email}`} className="btn-secondary px-3 py-2 text-sm">
              <Mail aria-hidden="true" className="size-4" />
              <span dir="ltr">{lead.email}</span>
            </a>
          )}
        </div>
      </header>

      {lead.client_id ? (
        <p role="status" className="card flex flex-wrap items-center gap-3 p-4">
          <UserCheck aria-hidden="true" className="size-5 text-success" />
          <span className="flex-1">{t("isClient")}</span>
          <Link href={`/clients/${lead.client_id}`} className="btn-secondary px-3 py-2 text-sm">
            {t("openClient")}
          </Link>
        </p>
      ) : (
        writable && (
          <section aria-labelledby="stage-heading" className="card flex flex-col gap-4 p-5">
            <h2 id="stage-heading" className="text-lg font-semibold">{t("stageTitle")}</h2>
            <StageControl leadId={lead.id} stage={lead.stage} lostReason={lead.lost_reason} />
            <form action={convertLead.bind(null, lead.id)} className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
              <SubmitButton>
                <UserCheck aria-hidden="true" className="size-4" />
                {t("convert")}
              </SubmitButton>
              <span className="text-sm text-muted">{t("convertHint")}</span>
            </form>
          </section>
        )
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <section aria-labelledby="activity-heading" className="card flex flex-col gap-4 p-5">
          <h2 id="activity-heading" className="text-lg font-semibold">{t("activityTitle")}</h2>
          {writable && <ActivityForm leadId={lead.id} />}
          <Timeline activities={lead.activities} locale={locale} timeZone={tenant.time_zone} />
        </section>

        <section aria-labelledby="details-heading" className="card flex flex-col gap-4 p-5">
          <h2 id="details-heading" className="text-lg font-semibold">{t("details")}</h2>
          <LeadForm
            action={updateLead.bind(null, lead.id)}
            owners={owners}
            lead={lead}
            submitLabel={t("save")}
            readOnly={!writable}
          />
          {writable && (
            <details className="border-t border-border pt-4 text-sm">
              <summary className="cursor-pointer text-danger">{t("delete")}</summary>
              <form action={deleteLead.bind(null, lead.id)} className="mt-3 flex flex-wrap items-center gap-3">
                <span>{t("deleteConfirm")}</span>
                <button type="submit" className="rounded-xl bg-danger px-3 py-2 font-semibold text-white dark:text-zinc-950">
                  {t("deleteYes")}
                </button>
              </form>
            </details>
          )}
        </section>
      </div>
    </main>
  );
}
