import { notFound } from "next/navigation";

import { RouteModal } from "@/components/ui/route-modal";
import { getTenantFor } from "@/lib/tenant";

import { ClientBody } from "../../../clients/[id]/client-body";

export default async function ClientModal({ params }: PageProps<"/clients/[id]">) {
  const { id } = await params;
  const { api, scope } = await getTenantFor("clients.read");
  const { data: client } = await api.GET("/clients/{client_id}", { params: { ...scope, path: { client_id: id } } });
  if (!client) notFound();
  const name = [client.first_name, client.last_name].filter(Boolean).join(" ");
  return (
    <RouteModal title={name} transitionName={`client-${id}`}>
      <ClientBody id={id} inModal />
    </RouteModal>
  );
}
