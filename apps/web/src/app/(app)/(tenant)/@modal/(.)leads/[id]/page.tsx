import { notFound } from "next/navigation";

import { RouteModal } from "@/components/ui/route-modal";

import { getCrm } from "../../../leads/crm";
import { LeadBody } from "../../../leads/[id]/lead-body";

export default async function LeadModal({ params }: PageProps<"/leads/[id]">) {
  const { id } = await params;
  const { api, scope } = await getCrm();
  const { data: lead } = await api.GET("/leads/{lead_id}", { params: { ...scope, path: { lead_id: id } } });
  if (!lead) notFound();
  const name = [lead.first_name, lead.last_name].filter(Boolean).join(" ");
  return (
    <RouteModal title={name} transitionName={`lead-${id}`}>
      <LeadBody id={id} inModal />
    </RouteModal>
  );
}
