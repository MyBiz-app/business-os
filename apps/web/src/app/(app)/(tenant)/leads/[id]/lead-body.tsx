import { Mail, Phone, UserCheck } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Avatar } from "@/components/avatar";
import { Ltr, UserText } from "@/components/bidi";
import { SubmitButton } from "@/components/form/submit-button";
import { unwrap } from "@/lib/api";
import { canWriteClients } from "@/lib/permissions";

import { convertLead, deleteLead, updateLead } from "../actions";
import { getCrm } from "../crm";
import { LeadForm } from "../lead-form";
import { ActivityForm, StageControl } from "./lead-controls";
import { MessagesSection } from "../../messages/messages-section";
import { Timeline } from "./timeline";
import { CollapsibleSection } from "@/components/ui/collapsible-section";

/** One lead: the page and the window over the leads list show the same thing. */
export async function LeadBody({ id, inModal = false }: { id: string; inModal?: boolean }) {
  const t = await getTranslations("leads");
  const locale = await getLocale();
  const context = await getCrm();
  const { tenant, api, scope } = context;
  const { data: lead, response } = await api.GET("/leads/{lead_id}", { params: { ...scope, path: { lead_id: id } } });
  if (response.status === 404 || !lead) notFound();
  const owners = unwrap(await api.GET("/leads/owners", { params: scope }));
  const writable = canWriteClients(tenant);
  const name = [lead.first_name, lead.last_name].filter(Boolean).join(" ");

  return (
    <div className="flex flex-col gap-6">
      {!inModal && (
        <Link href="/leads" className="text-sm text-primary-ink underline-offset-4 hover:underline">
          {t("back")}
        </Link>
      )}

      <header className="card-accent flex flex-wrap items-center gap-4 p-6">
        <Avatar id={lead.id} name={name} size="lg" />
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          {/* In a window the title bar already says the name. */}
          {inModal ? (
            <p dir="auto" className="truncate text-2xl font-extrabold tracking-tight">{name}</p>
          ) : (
            <h1 dir="auto" className="truncate text-3xl font-extrabold tracking-tight">{name}</h1>
          )}
          <p className="text-sm text-muted">
            {t(`stages.${lead.stage}`)} · {t(`sources.${lead.source}`)}
            {lead.campaign && <> · <UserText>{lead.campaign}</UserText></>}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {lead.phone && (
            <a href={`tel:${lead.phone}`} className="btn-secondary px-3 py-2 text-sm">
              <Phone aria-hidden="true" className="size-4" />
              <Ltr>{lead.phone}</Ltr>
            </a>
          )}
          {lead.email && (
            <a href={`mailto:${lead.email}`} className="btn-secondary px-3 py-2 text-sm">
              <Mail aria-hidden="true" className="size-4" />
              <Ltr>{lead.email}</Ltr>
            </a>
          )}
        </div>
      </header>

      {lead.client_id ? (
        <p role="status" className="card flex flex-wrap items-center gap-3 p-4">
          <UserCheck aria-hidden="true" className="size-5 text-success-ink" />
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

        <MessagesSection target={{ lead_id: lead.id }} phone={lead.phone} path={`/leads/${lead.id}`} context={context} />
      </div>

      <div className="grid gap-6">
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
            <CollapsibleSection variant="inline" className="border-t border-border pt-4 text-sm" triggerClassName="text-danger" title={t("delete")}>
              <form action={deleteLead.bind(null, lead.id)} className="flex flex-wrap items-center gap-3">
                <span>{t("deleteConfirm")}</span>
                <button type="submit" className="btn-danger">
                  {t("deleteYes")}
                </button>
              </form>
            </CollapsibleSection>
          )}
        </section>
      </div>
    </div>
  );
}
