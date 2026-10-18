import { notFound } from "next/navigation";

import { RouteModal } from "@/components/ui/route-modal";
import { getTenantFor } from "@/lib/tenant";

import { ClientBody } from "./[id]/client-body";

/** A client opened as a window over the list (`/clients?open=<id>`); the card grows into it. */
export async function ClientWindow({ id, closeHref }: { id: string; closeHref: string }) {
  const { api, scope } = await getTenantFor("clients.read");
  const { data: client } = await api.GET("/clients/{client_id}", { params: { ...scope, path: { client_id: id } } });
  if (!client) notFound();
  const name = [client.first_name, client.last_name].filter(Boolean).join(" ");
  return (
    <RouteModal title={name} transitionName={`client-${id}`} closeHref={closeHref}>
      <ClientBody id={id} inModal />
    </RouteModal>
  );
}
