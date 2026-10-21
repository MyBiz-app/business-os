import { Mail, Phone, UserCheck } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";

import { Avatar } from "@/components/avatar";
import { BackLink } from "@/components/back-link";
import { Ltr, UserText } from "@/components/bidi";
import { RecordHeader } from "@/components/layout/record-header";
import { RecordLayout, type RecordTab } from "@/components/record-layout";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
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

const STAGE_TONE: Record<string, BadgeTone> = { new: "info", contacted: "primary", trial: "warning", offer: "primary", won: "success", lost: "neutral" };

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

  const tabs: RecordTab[] = [
    {
      id: "details",
      label: t("nav.details"),
      content: (
        <>
          {lead.client_id ? (
            <Card as="p" role="status" className="flex flex-wrap items-center gap-3">
              <UserCheck aria-hidden="true" className="size-5 text-success-ink" />
              <span className="flex-1">{t("isClient")}</span>
              <ButtonLink href={`/clients/${lead.client_id}`} variant="secondary">
                {t("openClient")}
              </ButtonLink>
            </Card>
          ) : (
            writable && (
              <Card as="section" aria-labelledby="stage-heading" className="flex flex-col gap-4">
                <CardHeader title={t("stageTitle")} titleId="stage-heading" className="mb-0" />
                <StageControl leadId={lead.id} stage={lead.stage} lostReason={lead.lost_reason} />
                <form action={convertLead.bind(null, lead.id)} className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
                  <SubmitButton>
                    <UserCheck aria-hidden="true" className="size-4" />
                    {t("convert")}
                  </SubmitButton>
                  <span className="text-sm text-muted">{t("convertHint")}</span>
                </form>
              </Card>
            )
          )}

          <Card as="section" aria-labelledby="details-heading" className="flex flex-col gap-4">
            <CardHeader title={t("details")} titleId="details-heading" className="mb-0" />
            <LeadForm
              action={updateLead.bind(null, lead.id)}
              owners={owners}
              lead={lead}
              submitLabel={t("save")}
              readOnly={!writable}
            />
          </Card>

          {writable && (
            <CollapsibleSection variant="inline" className="card p-4 text-sm sm:p-5" triggerClassName="text-danger" title={t("delete")}>
              <form action={deleteLead.bind(null, lead.id)} className="flex flex-wrap items-center gap-3">
                <span>{t("deleteConfirm")}</span>
                <Button type="submit" variant="danger">
                  {t("deleteYes")}
                </Button>
              </form>
            </CollapsibleSection>
          )}
        </>
      ),
    },
    {
      id: "activity",
      label: t("nav.activity"),
      badge: lead.activities.length > 0 ? lead.activities.length : undefined,
      content: (
        <Card as="section" aria-labelledby="activity-heading" className="flex flex-col gap-4">
          <CardHeader title={t("activityTitle")} titleId="activity-heading" className="mb-0" />
          {writable && <ActivityForm leadId={lead.id} />}
          <Timeline activities={lead.activities} locale={locale} timeZone={tenant.time_zone} />
        </Card>
      ),
    },
    {
      id: "messages",
      label: t("nav.messages"),
      content: <MessagesSection target={{ lead_id: lead.id }} phone={lead.phone} path={`/leads/${lead.id}`} context={context} />,
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      {!inModal && <BackLink href="/leads" label={t("back")} />}

      <RecordHeader
        avatar={<Avatar id={lead.id} name={name} size="lg" />}
        name={name}
        inModal={inModal}
        badges={<Badge tone={STAGE_TONE[lead.stage] ?? "neutral"} dot>{t(`stages.${lead.stage}`)}</Badge>}
        subtitle={
          <>
            {t(`sources.${lead.source}`)}
            {lead.campaign && (
              <>
                {" · "}
                <UserText>{lead.campaign}</UserText>
              </>
            )}
          </>
        }
        actions={
          (lead.phone || lead.email) && (
            <>
              {lead.phone && (
                <ButtonLink href={`tel:${lead.phone}`} variant="secondary">
                  <Phone aria-hidden="true" className="size-4" />
                  <Ltr>{lead.phone}</Ltr>
                </ButtonLink>
              )}
              {lead.email && (
                <ButtonLink href={`mailto:${lead.email}`} variant="secondary">
                  <Mail aria-hidden="true" className="size-4" />
                  <Ltr>{lead.email}</Ltr>
                </ButtonLink>
              )}
            </>
          )
        }
      />

      <RecordLayout tabs={tabs} label={t("nav.label")} />
    </div>
  );
}
